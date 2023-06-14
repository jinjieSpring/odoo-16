# -*- coding: utf-8 -*-
from odoo.exceptions import UserError
from odoo.tools import safe_eval
from datetime import datetime
from odoo import api, models, fields

WORKFLOW_STATE = [('已取消', '已取消'), ('已终止', '已终止')]


class WorkflowMixln(models.AbstractModel):
    _name = 'hd.workflow.mixin'
    _description = 'Workflow Mixin'

    workflow_ids = fields.One2many('hd.workflow', 'res_id', domain=lambda self: [('res_model', '=', self._name), ('is_show', '=', True)], string='审批记录')
    workflow_look = fields.Boolean(string='审核按钮是否可见', default=False, compute='_compute_workflow_look', help='True')
    ir_process_id = fields.Many2one('ir.process', string='流程')
    attachment_ids = fields.One2many('ir.attachment', 'res_id', domain=lambda self: [('res_model', '=', self._name)], string='附件')
    attachment_number = fields.Integer(compute='_compute_attachment_number', string='附件数量')

    def _compute_workflow_look(self):
        for r in self:
            appr = self.env['hd.personnel.process.record'].search([('valid', '=', True),
                                                                   ('res_model', '=', self._name),
                                                                   ('res_id', '=', r.id),
                                                                   ('user_id', '=', self._uid)])
            r.workflow_look = True if appr else False

    def _compute_attachment_number(self):
        """附件上传"""
        attachment_data = self.env['ir.attachment'].read_group(
            [('res_model', '=', self._name), ('res_id', 'in', self.ids)], ['res_id'], ['res_id'])
        attachment = dict((data['res_id'], data['res_id_count']) for data in attachment_data)
        for expense in self:
            expense.attachment_number = attachment.get(expense.id, 0)

    @api.model
    def _default_states(self):
        return WORKFLOW_STATE

    def default_get(self, fields_list):
        result = super().default_get(fields_list)
        result['workflow_look'] = True
        return result

    @api.model_create_multi
    def create(self, vals_list):
        result = super().create(vals_list)
        result.create_workflow_new()
        return result

    def unlink(self):
        for order in self:
            if len(order.workflow_ids) > 1:
                raise UserError('已提交的单子无法删除!')
            else:
                order.workflow_ids.unlink()
                self.env['hd.personnel.process.record'].search(
                    [('res_model', '=', self._name), ('res_id', '=', order.id)]).unlink()
        return super().unlink()

    @api.model
    def search_read(self, domain=None, fields=None, offset=0, limit=None, order=None):
        logid = self.env.user.id
        do_type = self._context.get('do_type')
        if do_type == 'shenqing':
            domain.append(('create_uid', '=', logid))
        elif do_type == 'yiban':
            # 后期[]太长需要改变获取已办的方式
            domain.append(('id', 'in', [s.res_id for s in self.env['hd.personnel.process.record'].search([('user_id', '=', logid),
                                                                                                                   ('res_model', '=', self._name),
                                                                                                                   ('valid', '=', False)])]))
        elif do_type == 'all':
            pass
        else:
            domain.append(('id', 'in', [s.res_id for s in self.env['hd.personnel.process.record'].search([('valid', '=', True),
                                                                            ('res_model', '=', self._name),
                                                                            ('user_id', '=', logid)])]))
        return super().search_read(domain=domain, fields=fields, offset=offset, limit=limit, order=order)

    def action_confirm(self):
        context = dict(self._context or {})
        if 'hd.workflow.mixin' in self._inherit:
            main_record_finally_state = self.state
            context['depend_state'] = 'state'
        elif 'hd.workflow.mutil.mixin' in self._inherit:
            main_record_finally_state = getattr(self, self.depend_state)
            context['depend_state'] = self.depend_state
        # 再次赋值，应对新建一条后再创建moldel变为check.user表
        # context['active_model'] = self._name
        # context['active_id'] = self.id
        if main_record_finally_state != context['to_state']:
            raise UserError('警告：当前审批流程已发生改变，新刷新当前页面！')
        # 取process的信息, 审批人员res_users
        jump_workflows = []
        workflow_user_ids = []
        if self.ir_process_id:
            globals_dict = {'model': self}
            process_line_ids = self.ir_process_id.process_ids
            # 筛选process_line
            line_count = 0
            line = line_next_name = line_next = None
            records_model = self.env['ir.model'].sudo().search([('model', '=', self._name)], limit=1)
            cq_form = False
            for line_id in process_line_ids:
                if line_id.name == main_record_finally_state:
                    line = line_id
                    if line.approve_type == '串签':
                        c_records = self.env['hd.personnel.process.record'].search([('res_model', '=', self._name),
                                                                                    ('res_id', '=', self.id),
                                                                                    ('valid', '=', True)])
                        if len(c_records) > 1:
                            cq_form = True
                            line_next = line_id
                            break
                        else:
                            if not c_records.series_wound:
                                line_next = line_id
                                cq_form = True
                                break
                    if line.is_jump:
                        line_next_name = safe_eval.safe_eval(line.jump_code, globals_dict)
                    line_count += 1
                    continue
                if line_next_name:
                    if line_next:
                        continue
                    if line_next_name != line_id.name:
                        jump_workflows.append({
                            'name': line_id.name,
                            'note': '由系统跳过',
                            'model_id': records_model.id,
                            'res_id': self.id,
                            'type': line_id.approve_type,
                            'state': '同意',
                            'is_show': line_id.jump_record_show
                        })
                    else:
                        line_next = line_id
                else:
                    if line_count == 1 and not line_next:
                        line_next = line_id
            if line_count > 1:
                raise UserError('警告：系统流程配置错误！')
            else:
                # 设置串签、并签、汇签类型
                context['comfirm_state'] = '同意'
                context['ir_process_line_name'] = line.name
                # context['is_jump'] = line.is_jump
                context['jump_record_show'] = line.jump_record_show
                context['workflow_type'] = line_next.approve_type
                context['stop_flow'] = line_next.is_stop
                context['fixed_node'] = line_next.is_fixed
                context['ir_process_next_line_name'] = line_next.name
                context['jump_workflows'] = jump_workflows
                context['cq_form'] = cq_form
                if cq_form:
                    form_id = self.env.ref('hd_workflow.form_view_hd_approval_check_user_wizard_02').id
                    return {'type': 'ir.actions.act_window',
                            'res_model': 'hd.approval.check.user',
                            'name': '当前节点' + '  :  ' + context['ir_process_line_name'],
                            'view_mode': 'form',
                            'views': [(form_id, 'form')],
                            'target': 'new',
                            'context': context,
                            'flags': {'form': {'action_buttons': True}}}
                if line_next.type == '自定义':
                    workflow_user_ids = self.get_node_users(line_next.name)
                elif line_next.type == '固定审核人':
                    for r in line_next.users_ids:
                        workflow_user_ids.append(r.id)
                elif line_next.type == '权限组':
                    for r in line_next.groups_ids:
                        workflow_user_ids = workflow_user_ids + r.users.ids
                elif line_next.type == '角色组':
                    # hr_model = self.env['hr.employee'].sudo()
                    for w in line_next.workflow_role_ids:
                        if w.users_ids:
                            workflow_user_ids += w.users_ids.ids
                        else:
                            pass
                            # if w.code == 'total_applicant_first_leader':
                            #     # 申请人-科室领导
                            #     if self.create_uid.employee_ids.department_id:
                            #         dept_arr = self.create_uid.employee_ids.department_id.complete_name.split(' / ')
                            #         if len(dept_arr) == 3:
                            #             leader = self.env['hr.employee'].search(
                            #                 [('department_id.complete_name', 'ilike', dept_arr[0] + ' / ' + dept_arr[1]),
                            #                  ('hr_keshi_leader', '=', True)], limit=1)
                            #             if leader:
                            #                 workflow_user_ids = workflow_user_ids + [leader.user_id.id]
                            #         else:
                            #             workflow_user_ids = workflow_user_ids + [hr.user_id.id for hr in hr_model.search([('department_id', 'parent_of', self.create_uid.employee_ids.department_id.id), ('hr_keshi_leader', '=', True)])]
                            # elif w.code == 'total_applicant_dept_leader':
                            #     # 申请人-部门领导
                            #     if self.create_uid.employee_ids.department_id:
                            #         first_name = self.create_uid.employee_ids.department_id.complete_name.split(' / ')[0]
                            #         if first_name == '调试部':
                            #             workflow_user_ids = workflow_user_ids + [hr.user_id.id for hr in hr_model.search([('department_id.complete_name', '=', first_name+' / ' + '部门办'),
                            #                                                                                               ('hr_bumen_leader', '=', True)])]
                            #         else:
                            #             workflow_user_ids = workflow_user_ids + [hr.user_id.id for hr in hr_model.search([('department_id.complete_name', 'ilike', self.create_uid.employee_ids.department_id.complete_name.split(' / ')[0]), ('hr_bumen_leader', '=', True)])]
                            # elif w.code == 'total_applicant_inchargeof_leader':
                            #     # 申请人-分管领导
                            #     if self.create_uid.employee_ids.department_id:
                            #         fengguan_leaders = hr_model.search([('hr_fengguan_leader', '=', True)])
                            #         dept_id = self.create_uid.employee_ids.department_id.id
                            #         for fl in fengguan_leaders:
                            #            if fl.hr_mdept_ids.filtered_domain([('id', 'parent_of', dept_id)]):
                            #                workflow_user_ids.append(fl.user_id.id)
                            # elif w.code == 'total_before_node_applicant_inchargeof_leader':
                            #     # 上个节点-分管领导
                            #     fengguan_leaders = hr_model.search([('hr_fengguan_leader', '=', True)])
                            #     dept_id = self.env.user.employee_ids.department_id.id
                            #     for fl in fengguan_leaders:
                            #        if fl.hr_mdept_ids.filtered_domain([('id', 'parent_of', dept_id)]):
                            #            workflow_user_ids.append(fl.user_id.id)
                            # elif w.name in ['人力资源-请销假申请-部门考勤员', '部门预算员', '部门安全员']:
                            #     if self.create_uid.employee_ids.department_id:
                            #         if self._name == 'personnel.tpost':
                            #             com_name = self.callin_department.complete_name.split(' / ')[0]
                            #         else:
                            #             com_name = self.create_uid.employee_ids.department_id.complete_name.split(' / ')[0]
                            #         for u in w.maintain_ids:
                            #             if u.employee_ids.department_id and (com_name == u.employee_ids.department_id.complete_name.split(' / ')[0]):
                            #                 workflow_user_ids.append(u.id)
                            #                 break
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
            raise UserError('错误：未成功获取流程信息！')
        if context.get('external_create_order_next_node'):
            return self.env['hd.approval.check.user'].with_context(context).object_ok()
        # 处理审批人和多流程的时候
        form_id = self.env.ref('hd_workflow.form_view_hd_approval_check_user_wizard').id
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
        if 'hd.workflow.mixin' in self._inherit:
            context['depend_state'] = 'state'
            if self.state != context['to_state']:
                raise UserError('警告：当前审批流程已发生改变，新刷新当前页面！')
        elif 'hd.workflow.mutil.mixin' in self._inherit:
            context['depend_state'] = self.depend_state
            if getattr(self, self.depend_state) != context['to_state']:
                raise UserError('警告：当前审批流程已发生改变，新刷新当前页面！')
        form_id = self.env.ref('hd_workflow.form_view_hd_approval_check_user_wizard').id
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
        record_model = self.env['ir.model'].sudo().search([('model', '=', self._name)], limit=1)
        can_back_node = self._context.get('can_back_node')
        depend_state = 'state'
        if hasattr(self, 'depend_state'):
            depend_state = self.depend_state
        finally_can_back_node = can_back_node.get(depend_state)
        workflows = self.workflow_ids
        if workflows[0].state == '等待审批' and workflows[0].name in finally_can_back_node:
                # 处理在跳转后的节点与正常推动节点一样时,判断能否取回
                last_xinjian_record = workflows.filtered_domain([('name', '=', '新建')])
                after_records = self.env['hd.workflow'].search([('res_model', '=', self._name), ('res_id', '=', self.id), ('id', '>', last_xinjian_record[0].id), ('user_id', '=', False), ('name', '!=', workflows[0].name)])
                if len(after_records) == (finally_can_back_node.index(workflows[0].name)):
                    # 等于0并且为并签的时候要看是否有同意的情况
                    if len(after_records) == 0:
                       records = workflows.filtered_domain([('id', '>', last_xinjian_record[0].id), ('name', '=', workflows[0].name), ('state', '=', '同意')])
                       if records:
                           raise UserError('警告：无法取回,当前审批流程可能已流转，请刷新当前页面查看审批记录！')
                    write_records = self.env['hd.workflow'].search(
                            [('res_model', '=', self._name), ('res_id', '=', self.id), ('state', '=', '等待审批')])
                    self.write({depend_state: '新建'})
                    write_records.write({'refuse_to': '新建', 'state': '取回', 'note': '由发起人取回'})
                    self.env['hd.personnel.process.record'].with_context(active_model=self._name, active_id=self.id).create({
                        'name': workflows[0].name + '---->' + '新建',
                        'model_id': record_model.id,
                        'res_id': self.id,
                        'user_id': self._uid,
                    })
                else:
                    raise UserError('警告：无法取回,当前审批流程可能已流转，请刷新当前页面查看审批记录！')
        else:
            raise UserError('警告：无法取回,当前审批流程可能已流转，请刷新当前页面查看审批记录！')

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
                         'url': '/webuploader/index?res_model=%s&res_id=%s' % (self._name, self.id)}
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

    def create_workflow_new(self, depend_state='state'):
        self.ensure_one()
        records_model = self.env['ir.model'].sudo().search([('model', '=', self._name)], limit=1)
        self.write({'workflow_ids': [(0, 0, {'type': '汇签',
                                             'name': '新建',
                                             'model_id': records_model.id,
                                             'res_id': self.id,
                                             'create_id': self._uid,
                                             'user_id': self._uid,
                                             'state': '等待提交',
                                             'sequence': 1,
                                             'res_record_name': self.name
                                            })],
                    'ir_process_id': self.env['ir.process'].search([('model', '=', self._name),
                                                                    ('depend_state', '=', depend_state),
                                                                    ('active', '=', True)], order="id desc", limit=1).id
                    })
        self.env['hd.personnel.process.record'].create({
                    'name': '新建' + '---->' + '新建',
                    'model_id': records_model.id,
                    'res_id': self.id,
                    'user_id': self._uid})

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
        return self.env['hd.workflow']

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
        self.env['hd.personnel.process.record'].search([('res_model', '=', self._name), ('res_id', '=', self.id), ('valid', '=', True)]).write({
            'valid': False
        })


class WorkflowMutilMixln(models.AbstractModel):
    _name = 'hd.workflow.mutil.mixin'
    _inherit = 'hd.workflow.mixin'
    _description = 'Workflow Mutil Mixin'

    depend_state = fields.Char(string='依赖状态', compute='_compute_depend_state', store=True, default='state')
    finally_show_state_desc = fields.Char(string='最新状态', default='新建')

    def _compute_depend_state(self):
        pass

    @api.model_create_multi
    def create(self, vals_list):
        result = super().create(vals_list)
        result.create_workflow_new(depend_state=result.depend_state)
        return result