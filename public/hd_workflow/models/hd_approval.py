# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from datetime import datetime


class HdApprovalCheckUser(models.Model):
    _name = 'hd.approval.check.user'
    _description = '下级审核人'
    _order = 'id desc'

    name = fields.Text(string='审批建议/处理意见')
    state = fields.Selection([('同意', '同意'), ('拒绝', '拒绝')], string='审批操作', default='同意')
    form_state = fields.Char(string='表单状态')
    next_state = fields.Char(string='下一状态')
    sumbit_user_id = fields.Many2one('res.users', string='当前提交人', default=lambda self: self.env.user)
    sumbit_psignature = fields.Binary(string='个人签名', related='sumbit_user_id.psignature')
    check_user_ids = fields.One2many('hd.approval.check.user.line', 'order_id', string='审核人')
    users_ids = fields.One2many('hd.approval.message.user', 'order_id', string='消息通知人')
    stop_flow = fields.Boolean(default=False, string='停止工作流')
    send_email = fields.Boolean(string='已发过邮件', default=False)
    res_model = fields.Char(string='模块名')
    res_id = fields.Integer(string='数据id')
    refuse_state = fields.Selection(selection=lambda self: self._selection_refuse_state(), string='退回至')
    # type记录的是next_state的审批方式
    type = fields.Selection([('串签', '串签'), ('并签', '并签'), ('汇签', '汇签')], string='审批类型', default='汇签', help="""这个字段是存储下一个状态的审批规则,串签、并签、汇签，也就是
        串流、并流、择流。
        假设一份文件需要A、B两个主管来审批，那么，
        串签：A签完，才轮到B来签；一般A是小领导，B是大领导；
        并签：A和B是并列的，可同时签，但必须2人都要签；一般A和B是同一层级但不同部门领导
        汇签：A和B是并列的，但只需一个签就可以了；此处A、B就是完全等价的了""")
    fixed_node = fields.Boolean(string='固定审批人')

    @api.constrains('check_user_ids')
    def _check_check_user_ids(self):
        if self.state == '同意' and self.stop_flow is False and not self.check_user_ids:
            raise ValidationError("请添加下级审核人!")

    @api.onchange('state')
    def _onchange_state(self):
        if self.state == '拒绝':
            self.name = ''

    def _selection_refuse_state(self):
        active_id = self._context.get('active_id')
        model = self._context.get('active_model')
        state = self._context.get('to_state')
        if not active_id or not model:
            return []
        main_record = self.env[model].sudo().search([('id', '=', active_id)])
        selection_records = main_record.ir_process_id.process_ids
        state_sequence = selection_records.filtered_domain([('name', '=', state)]).sequence
        result = []
        state_list = main_record.workflow_ids
        for rec in state_list:
            rec_squence = selection_records.filtered_domain([('name', '=', rec.name)]).sequence
            if rec_squence < state_sequence:
                if not (rec['name'], rec['name']) in result:
                    if rec.user_id:
                        if rec.name == '新建':
                            result.append((rec['name'], rec['name']))
                            break
                        result.append((rec.name, rec.name))
        return result

    @api.model
    def default_get(self, fields):
        context = dict(self._context or {})
        res = super(HdApprovalCheckUser, self).default_get(fields)
        res['form_state'] = context.get('to_state')
        res['type'] = context.get('workflow_type')
        res['fixed_node'] = context.get('fixed_node')
        res['stop_flow'] = context.get('stop_flow')
        res['next_state'] = context.get('ir_process_next_line_name')
        res['res_model'] = context.get('active_model')
        res['res_id'] = context.get('active_id')
        res['state'] = context.get('comfirm_state')

        if context.get('stop_flow'):
            # 最后节点添加创建人为消息通知人。
            record = self.env[context.get('active_model')].sudo().search([('id', '=', context.get('active_id'))])
            if len(record.workflow_ids.filtered_domain([('state', '=', '等待审批')])) == 1:
                res['users_ids'] = [(0, 0, {'user_id': record.create_uid.id})]
        if context.get('workflow_user_ids'):
            lines = []
            n = datetime.now()
            for user_id in context.get('workflow_user_ids'):
                pram = {
                    'user_id': user_id
                }
                # shouquan_records = self.env['chown.model'].sudo().search(
                #     [('change_start', '<=', n), ('change_end', '>=', n),
                #      ('owner.user_id', '=', user_id), ('type', '=', '有效')], limit=1).chown_details.filtered(
                #     lambda t: t.desc == self._context['active_model'])
                # if shouquan_records:
                #     pram['certigier'] = shouquan_records.chowner.user_id.id
                #     pram['is_message'] = True
                lines.append((0, 0, pram))
            res['check_user_ids'] = lines
        if context.get('user_ids'):
            res['users_ids'] = []
            for user_id in context.get('user_ids'):
                res['users_ids'].append((0, 0, {
                    'user_id': user_id
                }))
        return res

    @api.model_create_multi
    def create(self, vals_list):
        for val in vals_list:
            if not val.get('name'):
                val['name'] = '同意'
        return super(HdApprovalCheckUser, self).create(vals_list)

    def but_confirm(self):
        if self.sumbit_user_id.psignature is False:
            raise UserError('请先设置个人签名!')
        else:
            if not self.check_user_ids and self._context.get('stop_flow') is False and (not self._context.get('cq_form')):
                raise ValidationError("请添加下级审核人!")
            self.common_confirm()
        return {'type': 'ir.actions.act_window_close'}

    def common_confirm(self):
        context = self._context
        main_record = self.env[context.get('active_model')].sudo().search([('id', '=', context.get('active_id'))])
        original_state = (getattr(main_record, context.get('depend_state')) if context.get('depend_state') else main_record.state)
        record_model = self.env['ir.model'].sudo().search([('model', '=', main_record._name)], limit=1)
        if context['to_state'] != original_state:
            raise UserError('警告：当前审批流程已发生改变，请刷新当前页面！')
        if self.state == '同意':
            self.object_ok(main_record, record_model, context)
        elif self.state == '拒绝':
            self.object_no(main_record, record_model, original_state, context)
        return True

    def object_ok(self, main_record, record_model, context):
        workflow_users_ids = context.get('workflow_user_ids') if context.get('external_create_order_next_node') else []
        messages_users_ids = [n.user_id.id for n in self.users_ids]
        record_check_user_ids = self.check_user_ids
        shouquan_dict = {}
        for x in record_check_user_ids:
            if x.certigier:
                # shouquan_dict[x.certigier.id] = '由' + x.user_id.name + '授权'
                workflow_users_ids.append(x.certigier.id)
            else:
                workflow_users_ids.append(x.user_id.id)
            if x.is_message:
                messages_users_ids.append(x.user_id.id)
        #::::有重复人不能提交
        if shouquan_dict:
            workflow_users_ids = list(set(workflow_users_ids))
        else:
            if len(workflow_users_ids) != len(set(workflow_users_ids)):
                raise UserError(u'警告：审核人重复！')
        # if messages_users_ids:
        #     messages_users_ids = list(set(messages_users_ids))
        execute_node_finish = True
        hd_workflow_env = self.env['hd.workflow']
        if context['to_state'] == '新建':
            if context['stop_flow'] is True:
                main_record.close_workflow_to_state(context.get('depend_state'),
                                                        context['ir_process_next_line_name'], '同意', '已关闭')
            else:
                hd_workflow_env.with_context(shouquan_dict=shouquan_dict).create_workflow_ok(main_record,
                                                                                             record_model,
                                                                                             self.type,
                                                                                             self.name,
                                                                                             context['ir_process_next_line_name'],
                                                                                             workflow_users_ids,
                                                                                             context.get('jump_workflows'),
                                                                                             context.get('depend_state'))
        else:
            # 判断等待审批没有则视为有拒绝，但是还要考虑全部审批过了的情况
            workflow_record = main_record.workflow_ids.filtered_domain([('state', '=', '等待审批')])
            if workflow_record:
                execute_node_finish = hd_workflow_env.with_context(shouquan_dict=shouquan_dict).create_workflow(main_record,
                                                                                                                    record_model,
                                                                                                                    self.type,
                                                                                                                    self.name,
                                                                                                                    context['ir_process_next_line_name'],
                                                                                                                    workflow_users_ids,
                                                                                                                    context.get('jump_workflows'),
                                                                                                                    context.get('depend_state'))
            else:
                execute_node_finish = hd_workflow_env.with_context(shouquan_dict=shouquan_dict).create_workflow_refuse(main_record,
                                                                                                                           record_model,
                                                                                                                           self.type,
                                                                                                                           self.name,
                                                                                                                           context['ir_process_line_name'],
                                                                                                                           context['ir_process_next_line_name'],
                                                                                                                           workflow_users_ids,
                                                                                                                           context.get('jump_workflows'),
                                                                                                                           context.get('depend_state'))
        # 执行节点结束事件
        if execute_node_finish:
            main_record.process_node_finish(context['ir_process_line_name'])
        # 发送消息，后期考虑是否及时发送
        # hd_workflow_env._send_sys_message(messages_users_ids, main_record)
        return True

    def object_no(self, main_record, record_model, original_state, context):
        if main_record.workflow_ids[0].state == '拒绝':
            # 连续拒绝
            self.env['hd.workflow'].write_workflow_refuse_repeatedly(main_record, record_model, self.name, self.refuse_state)
        else:
            # 单次拒绝
            self.env['hd.workflow'].write_workflow_refuse(main_record, record_model, self.name, self.refuse_state)
        # 先写入状态
        main_record.write({context.get('depend_state'): self.refuse_state})
        # 执行拒绝至某个节点后，执行回滚某些数据的操作
        main_record.refuse_to_node_finish(self.refuse_state, original_state)
        return True


class HdApprovalCheckUserLine(models.Model):
    _name = 'hd.approval.check.user.line'
    _description = '下级审核人'
    _order = 'sequence asc'

    sequence = fields.Integer(string=u'排序', default=1)
    user_id = fields.Many2one('res.users', string='用户')
    hd_weight = fields.Integer(string='权重')
    order_id = fields.Many2one('hd.approval.check.user', string='明细', ondelete='cascade', index=True, copy=False)
    is_message = fields.Boolean(default=False, string='是否发送消息')
    certigier = fields.Many2one('res.users', string='被授权人')

    @api.onchange('user_id')
    def _compute_certigier(self):
        n = datetime.now()
        # shouquan_records = self.env['chown.model'].sudo().search([('change_start', '<=', n), ('change_end', '>=', n), ('owner.user_id', '=', self.user_id.id), ('type', '=', '有效')], limit=1)
        # if self._context['active_model']:
        #     now_shouquan_model = shouquan_records.chown_details.filtered(lambda t: t.desc == self._context['active_model'])
        #     self.certigier = now_shouquan_model.chowner.user_id


class HdApprovalMessageUser(models.Model):
    _name = 'hd.approval.message.user'
    _description = '消息通知人'
    _order = 'sequence asc'

    sequence = fields.Integer(string=u'排序', default=1)
    user_id = fields.Many2one('res.users', string=u'用户')
    send_email = fields.Boolean(string="邮件", default=True)
    order_id = fields.Many2one('hd.approval.check.user', string='明细', ondelete='cascade', index=True, copy=False)
    is_send = fields.Boolean(string="是否发送过", default=False)

    def send_message_email(self):
        records = self.search([('send_email', '=', True), ('is_send', '=', False)])
        temp_id = self.env.ref('hd_workflow.workflow_message_template', raise_if_not_found=False)
        if temp_id:
            for r in records:
                message_id = temp_id.send_mail(res_id=r.id, force_send=True)
                if message_id:
                    r.is_send = True

