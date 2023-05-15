# -*- coding: utf-8 -*-

from odoo.exceptions import UserError
from odoo.tools import safe_eval
from datetime import datetime
from odoo import api, models, fields


class WorkflowMixln(models.AbstractModel):
    _name = 'hd.workflow.mixin'
    _description = 'Workflow Mixin'

    state = fields.Selection(selection=lambda self: self._default_states(), string='审核状态')
    workflow_ids = fields.One2many('hd.workflow', 'res_id', domain=lambda self: [('res_model', '=', self._name), ('is_show', '=', True)], string='审批记录')
    workflow_look = fields.Boolean(string='审核按钮是否可见', default=False, compute='_compute_workflow_look', help='True')
    depend_state = fields.Char(string='依赖状态', compute='_compute_depend_state', store=True, default='state')
    finally_show_state_desc = fields.Char(string='最新状态', default='新建')
    ir_process_id = fields.Many2one('ir.process', string='流程')
    line_buttons = fields.Json(string='button属性', compute="_compute_line_buttons", store=True, copy=True, readonly=False)
    attachment_ids = fields.One2many('ir.attachment', 'res_id', domain=lambda self: [('res_model', '=', self._name)], string='附件')
    attachment_number = fields.Integer(compute='_compute_attachment_number', string='附件数量')

    @api.model
    def _default_states(self):
        return [('已终止', '已终止'), ('已取消', '已取消'), ('已废弃', '已废弃')]

    def action_confirm(self):
        #self.ensure_one()
        context = dict(self._context or {})
        # 再次赋值，应对新建一条后再创建molde变为check.user表
        context['active_model'] = self._name
        context['active_id'] = self.id
        context['comfirm_state'] = '同意'
        finally_main_record_state_desc = getattr(self, self.depend_state)
        if getattr(self, self.depend_state) != context['to_state']:
            raise UserError(u'警告：当前审批流程已发生改变，新刷新当前页面！')
        # if context['to_state'] == '新建' and self.create_uid.id != self._uid:
        #     raise UserError(u'警告：当前数据非您发起无法提交！')
        # 取process的信息
        jump_workflows = []
        # 审批人员res_users
        workflow_user_ids = []
        if self.ir_process_id:
            # 筛选process_line
            lines = self.ir_process_id.process_ids
            line = lines.filtered(lambda o: o.name == finally_main_record_state_desc)
            if len(line) > 1:
                raise UserError(u'警告：系统流程配置错误！')
            else:
                # 取line的下一个节点，因为配置的东西全在这个节点上
                line_next = lines.filtered(lambda o: o.sequence == (line.sequence + 1))
                # 判断line是不是有跳转
                if line.is_jump:
                    #执行方法
                    globals_dict = {'model': self}
                    line_name = safe_eval.safe_eval(line.jump_code, globals_dict) or line_next.name
                    line_next = lines.filtered(lambda o: o.name == line_name)
                    copy_line = line
                    records_model = self.env['ir.model'].sudo().search([('model', '=', self._name)], limit=1)
                    while copy_line.next_id.name != line_next.name:
                        jump_workflows.append({
                            'name': copy_line.next_id.name,
                            'note': '由系统跳过',
                            'model_id': records_model.id,
                            'res_id': self.id,
                            'type': copy_line.next_id.approve_type,
                            'state': '同意',
                            'is_show': line.jump_record_show
                        })
                        copy_line = copy_line.next_id
                # 设置串签、并签、汇签类型
                context['workflow_type'] = line_next.approve_type
                context['stop_flow'] = line_next.is_stop
                context['fixed_node'] = line_next.is_fixed
                context['ir_process_line_name'] = line.name
                context['ir_process_next_line_name'] = line_next.name
                context['is_jump'] = line.is_jump
                context['jump_record_show'] = line.jump_record_show
                context['jump_workflows'] = jump_workflows
                if line_next.type == '自定义':
                    workflow_user_ids = self.get_node_users(line_next.name)
                elif line_next.type == '固定审核人':
                    for r in line_next.users_ids:
                        workflow_user_ids.append(r.id)
                elif line_next.type == '权限组':
                    for r in line_next.groups_ids:
                        workflow_user_ids = workflow_user_ids + r.users.ids
                elif line_next.type == '角色组':
                    hr_model = self.env['hr.employee'].sudo()
                    for w in line_next.workflow_role:
                        if w.code == 'total_applicant_first_leader':
                            # 申请人-科室领导
                            if self.create_uid.employee_ids.department_id:
                                dept_arr = self.create_uid.employee_ids.department_id.complete_name.split(' / ')
                                if len(dept_arr) == 3:
                                    leader = self.env['hr.employee'].search(
                                        [('department_id.complete_name', 'ilike', dept_arr[0] + ' / ' + dept_arr[1]),
                                         ('hr_keshi_leader', '=', True)], limit=1)
                                    if leader:
                                        workflow_user_ids = workflow_user_ids + [leader.user_id.id]
                                else:
                                    workflow_user_ids = workflow_user_ids + [hr.user_id.id for hr in hr_model.search([('department_id', 'parent_of', self.create_uid.employee_ids.department_id.id), ('hr_keshi_leader', '=', True)])]
                        elif w.code == 'total_applicant_dept_leader':
                            # 申请人-部门领导
                            if self.create_uid.employee_ids.department_id:
                                first_name = self.create_uid.employee_ids.department_id.complete_name.split(' / ')[0]
                                if first_name == '调试部':
                                    workflow_user_ids = workflow_user_ids + [hr.user_id.id for hr in hr_model.search([('department_id.complete_name', '=', first_name+' / ' + '部门办'),
                                                                                                                      ('hr_bumen_leader', '=', True)])]
                                else:
                                    workflow_user_ids = workflow_user_ids + [hr.user_id.id for hr in hr_model.search([('department_id.complete_name', 'ilike', self.create_uid.employee_ids.department_id.complete_name.split(' / ')[0]), ('hr_bumen_leader', '=', True)])]
                        elif w.code == 'total_applicant_inchargeof_leader':
                            # 申请人-分管领导
                            if self.create_uid.employee_ids.department_id:
                                fengguan_leaders = hr_model.search([('hr_fengguan_leader', '=', True)])
                                dept_id = self.create_uid.employee_ids.department_id.id
                                for fl in fengguan_leaders:
                                   if fl.hr_mdept_ids.filtered_domain([('id', 'parent_of', dept_id)]):
                                       workflow_user_ids.append(fl.user_id.id)
                        elif w.code == 'total_before_node_applicant_inchargeof_leader':
                            # 上个节点-分管领导
                            fengguan_leaders = hr_model.search([('hr_fengguan_leader', '=', True)])
                            dept_id = self.env.user.employee_ids.department_id.id
                            for fl in fengguan_leaders:
                               if fl.hr_mdept_ids.filtered_domain([('id', 'parent_of', dept_id)]):
                                   workflow_user_ids.append(fl.user_id.id)
                        elif w.name in ['人力资源-请销假申请-部门考勤员', '部门预算员', '部门安全员']:
                            if self.create_uid.employee_ids.department_id:
                                if self._name == 'personnel.tpost':
                                    com_name = self.callin_department.complete_name.split(' / ')[0]
                                else:
                                    com_name = self.create_uid.employee_ids.department_id.complete_name.split(' / ')[0]
                                for u in w.maintain_ids:
                                    if u.employee_ids.department_id and (com_name == u.employee_ids.department_id.complete_name.split(' / ')[0]):
                                        workflow_user_ids.append(u.id)
                                        break
                        elif w.name in ['人力资源-资质津贴-人力经办人',
                                        '人力资源领域负责人',
                                        '综合行政-会务活动申请-综合管理部经办人',
                                        '综合行政-办公用品-办公用品管理员',
                                        '综合行政-宿舍申请-宿舍申请管理员',
                                        '综合行政-疫情防控员工外出-接口人',
                                        '综合行政-一卡通申请-制卡人',
                                        '综合行政-一卡通申请-经办人',
                                        '综合行政-一卡通申请-财务部',
                                        '综合行政-总办会-议题管理者',
                                        '综合行政-疫情防控外来人员-接口人',
                                        '综合行政-综合管理-接待用酒申请经办人',
                                        '综合行政-车证申请-车证管理员',
                                        '综合行政-行政管理-公文管理员',
                                        '综合行政-印章使用申请-印章管理者',
                                        '维修申请-办公区接口人',
                                        '维修申请-生活区接口人',
                                        '文档管理-函文处理单-函文管理员',
                                        '信息化-功能开发-开发需求申请-组织研发评审',
                                        '文档管理-图书管理-图书管理员',
                                        '文档管理-图书管理-图书采购员',
                                        '文档管理-图书管理-预算管理员',
                                        '文档管理-图书管理-财务科',
                                        '会议室预定处理人',
                                        '综合管理部主任',
                                        'HSE管理-劳保台账-物资管理员',
                                        '安全质量与技术部主任',
                                        '党建管理-意见征集-党务专员',
                                        '党建管理-意见征集-分公司党委',
                                        '党委会议题管理者',
                                        '党费负责人及验收人',
                                        '会计--党费',
                                        '核二院',
                                        '财务审核',
                                        '财务部负责人',
                                        '物业',
                                        '党群工作部负责人',
                                        '计划合同部负责人',
                                        '分公司安专费预算员',
                                        '分公司计划管理员',
                                        '合同管理-营业执照-计划合同部经办人',
                                        '分公司总经理',
                                        '财务管理-汇款申请-经办会计']:
                            workflow_user_ids = workflow_user_ids + w.maintain_ids.ids
                elif line_next.type == '节点审核人':
                    for r in line_next.before_ids:
                        if r.name == '新建':
                            workflow_user_ids.append(self.create_uid.id)
                        elif r.type == '固定审核人':
                            workflow_user_ids = workflow_user_ids + r.users_ids.ids
                context['workflow_user_ids'] = workflow_user_ids
                # 读取消息发送人
                context['user_ids'] = self.get_node_users_for_message(line_next.name)
        else:
            raise UserError(u'错误：当前流程未配置！')
        if context.get('external_create_order_next_node'):
            return self.env['hd.approval.check.user'].with_context(context).object_ok()
        # 处理审批人和多流程的时候
        form_id = self.env.ref('hd_workflow.view_form_amos_approval_check_user_wizard_01').id
        return {'type': 'ir.actions.act_window',
                'res_model': 'hd.approval.check.user',
                'name': '下一阶段' + '  ⇒  ' + context['ir_process_next_line_name'],
                'view_mode': 'form',
                'views': [(form_id, 'form')],
                'target': 'new',
                'context': context,
                'flags': {'form': {'action_buttons': True}}}

    def action_confirm_refuse(self):
        self.ensure_one()
        context = dict(self._context or {})
        # 再次赋值，应对新建一条后再创建molde变为check.user表
        context['active_model'] = self._name
        context['active_id'] = self.id
        context['comfirm_state'] = '拒绝'
        # context['form_state'] = self.state
        #::::判断这个工作流是不是已存在存在执行提醒 并刷新 当前用户流程已存在，或已在其它地方登陆并操作
        domain = [('model', '=', self._name), ('active', '=', True)]
        if hasattr(self, 'depend_state'):
            domain.append(('depend_state', '=', self.depend_state))
            context['depend_state'] = self.depend_state
            if getattr(self, self.depend_state) != context['to_state']:
                raise UserError(u'警告：当前审批流程已发生改变，新刷新当前页面！')
        else:
            context['depend_state'] = 'state'
            if self.state == context['to_state']:
                pass
            else:
                raise UserError(u'警告：当前审批流程已发生改变，新刷新当前页面！')
        form_id = self.env.ref('hd_workflow.view_form_amos_approval_check_user_wizard_01').id
        return {'type': 'ir.actions.act_window',
                'res_model': 'hd.approval.check.user',
                'name': '当前阶段' + '  :  ' + context['to_state'],
                'view_mode': 'form',
                'views': [(form_id, 'form')],
                'target': 'new',
                'context': context,
                'flags': {'form': {'action_buttons': True}}}

    def action_back(self):
        """
        开始进行撤销,包含多流程, 并签的话则有个审批就不能退回
        """
        can_back_node = self._context.get('can_back_node')
        depend_state = 'state'
        if hasattr(self, 'depend_state'):
            depend_state = self.depend_state
        finally_can_back_node = can_back_node.get(depend_state)
        workflows = self.workflow_ids
        if workflows[0].state == '等待审批' and workflows[0].name in finally_can_back_node:
                # 处理在跳转后的节点与正常推动节点一样时,判断能否取回
                last_xinjian_record = workflows.filtered_domain([('name', '=', '新建')])
                after_records = self.env['hd.workflow'].sudo().search([('res_model', '=', self._name), ('res_id', '=', self.id), ('id', '>', last_xinjian_record[0].id), ('user_id', '=', False), ('name', '!=', workflows[0].name)])
                if len(after_records) == (finally_can_back_node.index(workflows[0].name)):
                    # 等于0并且为并签的时候要看是否有同意的情况
                    if len(after_records) == 0:
                       records = workflows.filtered_domain([('id', '>', last_xinjian_record[0].id), ('name', '=', workflows[0].name), ('state', '=', '同意')])
                       if records:
                           raise UserError('警告：无法取回,当前审批流程可能已流转，请刷新当前页面查看审批记录！')
                    write_records = self.env['hd.workflow'].sudo().search(
                            [('res_model', '=', self._name), ('res_id', '=', self.id), ('state', '=', '等待审批')])
                    self.write({depend_state: '新建'})
                    write_records.write({'refuse_to': '新建', 'state': '取回', 'note': '由发起人取回'})
                    self.env['hd.personnel.process.record'].with_context(active_model=self._name, active_id=self.id).sudo().create({
                        'name': workflows[0].name + '---->' + '新建',
                        'res_model': self._name,
                        'res_id': self.id,
                        'user_id': self._uid,
                    })
                else:
                    raise UserError('警告：无法取回,当前审批流程可能已流转，请刷新当前页面查看审批记录！')
        else:
            raise UserError('警告：无法取回,当前审批流程可能已流转，请刷新当前页面查看审批记录！')

    def _compute_workflow_look(self):
        for r in self:
            appr = self.env['hd.personnel.process.record'].sudo().search([('valid', '=', '有效'),
                                                                     ('res_model', '=', self._name),
                                                                     ('res_id', '=', r.id),
                                                                     ('user_id', '=', self._uid)])
            if appr:
                r.workflow_look = True
            else:
                r.workflow_look = False

    def _compute_attachment_number(self):
        """附件上传"""
        attachment_data = self.env['ir.attachment'].read_group(
            [('res_model', '=', self._name), ('res_id', 'in', self.ids)], ['res_id'], ['res_id'])
        attachment = dict((data['res_id'], data['res_id_count']) for data in attachment_data)
        for expense in self:
            expense.attachment_number = attachment.get(expense.id, 0)

    def _compute_depend_state(self):
        for s in self:
            s.depend_state = 'state'

    @api.depends('ir_process_id.process_ids')
    def _compute_line_buttons(self):
        for s in self:
            s.line_buttons = {'name': 'action_confirm',
                              'states': '新建',
                              'string': '提交',
                              'type': 'object',
                              'class': 'oe_highlight',
                              'attrs': "{'invisible': ['|','!',('create_uid','=', uid)]}",
                              'context': "{'to_state': state}"}

    def action_get_attachment_view(self):
        """附件上传动作视图"""
        self.ensure_one()
        address_form_id = self.env.ref('hd_workflow.view_basic_attachment').id
        return {'type': 'ir.actions.act_window',
                'name': '上传文件',
                'res_model': 'ir.attachment',
                'view_mode': 'form',
                'views': [(address_form_id, 'form')],
                'target': 'new',
                'flags': {'form': {'action_buttons': False}},
                'domain': [('res_model', '=', self._name), ('res_id', 'in', self.ids)],
                'context': {'default_res_model': self._name, 'default_res_id': self.id}
                }

    def add_big_attachment(self):
        client_action = {'type': 'ir.actions.act_url',
                         'name': "超大文件上传",
                         'target': 'new',
                         'nodestroy': True,
                         'url': '/webuploader/index?res_model=%s&res_id=%s' % (self._name, self.id),
                        }
        return client_action

    def jump_condition(self):
        """
            该方法state的值,返回值必须是在当前表单状态之后的状态，否则会出现死循环
        """
        return None

    def process_node_finish(self, state):
        """
            该方法是在state写入后执行的,所以state为提交时的节点名称，即A→B的过程中的A
        """
        print('在%s节点,开始操作' % state)

    def refuse_to_node_finish(self, state, original_state):
        """
            该方法是在state写入后执行的,所以state为拒绝至节点的名字，即B拒绝到A中的A
        """
        print('拒绝至%s节点,开始操作' % state)

    def get_node_users(self, state):
        """
            该方法直接返回res_user为id的人员数组, 其中state为提交后的节点名称，即A→B的过程中的B
        """
        return []

    def get_node_users_for_message(self, state):
        """
            该方法直接返回res_user为id的人员数组, 其中state为提交后的节点名称，即A→B的过程中的B
        """
        return []

    def create_workflow_new(self, record):
        records_model = self.env['ir.model'].sudo().search([('model', '=', self._name)], limit=1)
        # if hasattr(record, 'depend_state'):
        #     record.finally_show_state_desc = '新建'
        record.workflow_ids = [(0, 0, {
            'type': '汇签',
            'name': '新建',
            'model_id': records_model.id,
            'res_id': record.id,
            'create_id': self._uid,
            'user_id': self._uid,
            'state': '等待提交',
            'sequence': 1,
            'res_record_name': record.name
        })]
        self.env['hd.personnel.process.record'].with_context({'active_model': record._name, 'active_id': record.id}).sudo().create({
                    'name': '新建' + '---->' + '新建',
                    'model_id': records_model.id,
                    'res_id': record.id,
                    'user_id': self._uid})
        # 直接提交事务，让后期主数据的workflow_ids能挂载查询
        self.env.cr.commit()

    def get_print_workflow(self, state_desc):
        """
            该方法直接返回最终的有效的记录
        """
        state_desc_arr = []
        state_list = self.workflow_ids.filtered_domain([('state', '!=', '取回')])
        state = getattr(self, self.depend_state) if hasattr(self, 'depend_state') else self.state
        state_field = self.env['ir.model.fields']._get(self._name, self.depend_state if hasattr(self, 'depend_state') else 'state')
        for s_d in state_field.selection_ids:
            if s_d.name == state:
                break
            else:
                state_desc_arr.append(s_d.name)
        if state_desc in state_desc_arr:
            search_record = state_list.filtered_domain([('name', '=', state_desc)])
            if search_record:
                first_version_id = search_record[0].version_id
                if not first_version_id:
                   return search_record.filtered_domain([('version_id', '=', False)])
                else:
                   record_ids = []
                   for sr in search_record:
                       if sr.version_id == first_version_id:
                           record_ids.append(sr.id)
                   return search_record.filtered_domain(([('id', 'in', record_ids)]))
        return self.env['hd.workflow'].sudo()

    def close_workflow_to_state(self, depend_state, state, note, workflow_state):
        """
            该方法用于直接关闭当前工作流和待办且刷新节点
        """
        self.write({depend_state: state})
        self.workflow_ids.filtered_domain([('state', 'in', ['等待提交', '等待审批'])]).write({
            'note': note,
            'state': workflow_state,
            'end_date': datetime.now()
        })
        self.env['hd.personnel.process.record'].search([('res_model', '=', self._name), ('res_id', '=', self.id), ('valid', '=', '有效')]).write({
            'valid': '无效'
        })
