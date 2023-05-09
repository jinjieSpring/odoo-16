# -*- coding: utf-8 -*-
from odoo import fields, models, api, modules
from datetime import datetime


class HdWorkflow(models.Model):
    _name = 'hd.workflow'
    _description = '工作流记录'
    _order = 'id desc'

    name = fields.Char(string='所在节点', index=True)
    model_id = fields.Many2one('ir.model', string='对象')
    res_model_id = fields.Integer(string='对象ID', related='model_id.id', store=True)
    res_model = fields.Char(string='对象名称', related='model_id.model', store=True)
    res_id = fields.Integer(string='记录ID', group_operator=False)
    res_record_name = fields.Char(string='数据名称', help="该字段用于总待办的时候查询")
    user_id = fields.Many2one('res.users', string='审批人')
    accredit = fields.Char(string='授权信息', default='无')
    create_id = fields.Many2one('res.users', string='记录创建人')
    start_date = fields.Datetime(string='记录申请时间', default=fields.Datetime.now)
    end_date = fields.Datetime(string='审批日期')
    note = fields.Text('审批意见')
    refuse_to = fields.Char(string='退回至')
    form_view = fields.Char(string='视图地址')
    sequence = fields.Integer(string='排序', default=1)
    type = fields.Selection([('汇签', '汇签'), ('串签', '串签'), ('并签', '并签')], string='类型', default='汇签', help="""串签、并签、汇签，也就是
    串流、并流、择流。
    假设一份文件需要A、B两个主管来审批，那么，
    串签：A签完，才轮到B来签；一般A是小领导，B是大领导；
    并签：A和B是并列的，可同时签，但必须2人都要签；一般A和B是同一层级但不同部门领导
    汇签：A和B是并列的，但只需一个签就可以了；此处A、B就是完全等价的了""")
    state = fields.Selection([
        ('等待提交', '等待提交'),
        ('已提交', '已提交'),
        ('同意', '同意'),
        ('拒绝', '拒绝'),
        ('等待审批', '等待审批'),
        ('已关闭', '已关闭')], string='审批状态', default='等待审批', index=True)
    version_id = fields.Integer(string='版本', help='记录拒绝后的workflowid用于取第几次拒绝后的数据', default=None)
    is_show = fields.Boolean(string='显示', default=True, help="""是否显示该工作流记录""")

    @api.model_create_multi
    def create(self, vals_list):
        return super(HdWorkflow, self).create(vals_list)

    def read(self, fields=None, load='_classic_read'):
        """ 绕过当前ORM. """
        self.check_access_rule('read')
        return super(HdWorkflow, self).read(fields=fields, load=load)

    def send_message(self, records, content, author_id, partner_ids):
        #::::发送审批消息
        url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        lines = []
        for partner_id in partner_ids:
            pram = {
                'res_partner_id': partner_id,
            }
            lines.append((0, 0, pram))

        message = self.env['mail.message'].create({
            'record_name': records.name,
            'subject': '消息通知',
            'body': content or '<a style="font-size:20px" href="%s/web#model=%s&id=%s" target="_blank">请您阅知</a><br>' % (url, records._name, records.id),
            'message_type': 'notification',
            'res_id': records.id,
            'model': records._name,
            'subtype_id': 2,  # id=2 是备注
            'author_id': author_id,
            'notification_ids': lines,
        })
        return message

    def _send_sys_message(self, users, record):
        url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        odoobot_id = self.env['ir.model.data']._xmlid_to_res_id('base.partner_root')
        for user in self.env['res.users'].sudo().search([('id', 'in', users)]):
            channel = self.env['mail.channel'].sudo().search([('channel_type', '=', 'chat'), ('name', '=', 'OdooBot, ' + user.partner_id.name)], limit=1)
            if not channel:
                user.sudo().write({'odoobot_state': 'not_initialized'})
                channel = self.env['mail.channel'].with_user(user).sudo().init_odoobot()
            channel.sudo().message_post(
                body='<a style="font-size:16px" href="%s/web#model=%s&id=%s" target="_blank">%s:%s需您阅知,请点击查看</a>' % (url, record._name, record.id, record._description, record.name),
                author_id=odoobot_id,
                message_type="comment",
                subtype_xmlid="mail.mt_comment"
            )

    def create_workflow(self, records, type='汇签', message='同意', state_name='', workflow_users_ids=[], jump_workflows=[], depend_state='state'):
        """
        创建下级用户工作流和更新当前工作流状态
        :param records:
        :param content:
        :return:
        """
        now = datetime.now()
        others_count = self.write_workflow(records, message, now)
        if others_count == 0:
            records_model = self.env['ir.model'].sudo().search([('model', '=', records._name)], limit=1)
            v_list = jump_workflows
            # 还要读取together的表取出其他人提交的人进行去重
            bingqian_records = self.env['hd.workflow.together'].sudo().search(
                [('res_model', '=', records._name), ('res_id', '=', records.id), ('name', '=', state_name), ('version_id', '=', None)])
            bingqian_workflow_users_ids = []
            for b in bingqian_records:
                bingqian_workflow_users_ids.append(b.user_id.id)
            pr_list = []
            for user in list(set(workflow_users_ids+bingqian_workflow_users_ids)):
                v_list.append({
                    'type': type,
                    'name': state_name,
                    'model_id': records_model.id,
                    'res_id': records.id,
                    'create_id': self._uid,
                    'start_date': now,
                    'user_id': user,
                    'state': '等待审批',
                    'accredit': self._context.get('shouquan_dict').get(user) or '无',
                    'sequence': 3,
                    'res_record_name': records.name
                })
                pr_list.append({
                    'name': self._context.get('ir_process_line_name') + '---->' + state_name,
                    'res_model': records._name,
                    'res_id': records.id,
                    'user_id': user,
                })
            self.create(v_list)
            self.env['hd.personnel.process.record'].sudo().create(pr_list)
            records.write({depend_state: state_name})
            return True
        else:
            #创建在togethers表里
            self.env['hd.workflow.together'].create_workflow(records, type, message, state_name, workflow_users_ids)
            return False

    def write_workflow(self, records, message='同意', t = datetime.now()):
        """
        更新当前用户工作流
        :param records:
        :param content:
        :return:
        """
        workflow_record = self.search([('res_model', '=', records._name), ('res_id', '=', records.id), ('state', '=', '等待审批'), ('user_id', '=', self._uid)], limit=1)
        if workflow_record:
            # others_count标识并签自己那条记录刷掉后还没有其他记录，有则不创建
            others_count = 0
            if workflow_record.type == '汇签':
                workflow_other_records = self.search([('res_model', '=', records._name), ('res_id', '=', records.id), ('state', '=', '等待审批'), ('id', '!=', workflow_record.id)])
                workflow_other_records.write({'state': '已关闭', 'note': '由 %s 汇签' % workflow_record.user_id.name, 'end_date': t})
            elif workflow_record.type == '并签' or workflow_record.type == '串签':
                workflow_other_records = self.search(
                    [('res_model', '=', records._name), ('res_id', '=', records.id), ('state', '=', '等待审批'),
                     ('id', '!=', workflow_record.id)])
                others_count = len(workflow_other_records)
            workflow_record.write({'state': '同意', 'note': message, 'end_date': t})
            self.env['hd.personnel.process.record'].sudo().search([('res_model', '=', records._name),
                                                                     ('res_id', '=', records.id),
                                                                     ('valid', '=', '有效'), ('user_id', '=', self._uid)]).write({'valid': '无效'})
            return others_count

    def write_workflow_refuse(self, records, message='同意', refuse_to=''):
        t = datetime.now()
        my_refuse_id = ""
        pr_list = []
        for w in records.workflow_ids.filtered_domain([('state', '=', '等待审批')]):
            if w.user_id.id == self._uid:
                my_refuse_id = w.id
                w.write({'state': '拒绝''', 'note': message, 'end_date': t, 'refuse_to': refuse_to})
            else:
                w.write({'state': '拒绝', 'note': '由 %s 拒绝' % self.env.user.name, 'end_date': t, 'refuse_to': refuse_to})
        # 在处理拒绝后把version_id刷成当前拒绝后的id
        records.workflow_ids.filtered_domain([('version_id', '=', 0)]).write({'version_id': my_refuse_id})
        # 处理拒绝后把together表version_id刷成当前拒绝后的id
        self.env['hd.workflow.together'].search([('res_model', '=', records._name),
                                                   ('res_id', '=', records.id),
                                                   ('version_id', '=', None)]).write({'version_id': my_refuse_id})
        # 插入hd.personnel.process.record
        other_version_id = my_refuse_id
        pick_times = 0
        for b in records.workflow_ids.filtered_domain([('state', '!=', '取回'), ('name', '=', refuse_to)]):
            if pick_times == 0:
                other_version_id = b.version_id
            if other_version_id != b.version_id:
                break
            pr_list.append({
                'name': self._context.get('to_state') + '---->' + refuse_to,
                'res_id': records.id,
                'res_model': records._name,
                'user_id': b.user_id.id,
            })
            # other_version_id = b.version_id
            pick_times += 1
        self.env['hd.personnel.process.record'].sudo().create(pr_list)
        return True

    def write_workflow_refuse_repeatedly(self, records, message='同意', refuse_to=''):
        t = datetime.now()
        # 记录当前节点状态，取workflow_ids[0].refuse_to
        node_state = records.workflow_ids[0].refuse_to
        first_refuse_id = ''
        for r in records.workflow_ids:
            if r.state == '拒绝':
                first_refuse_id = r.version_id
            else:
                break
        # 必须要让不是自己的节点先生成
        v_list_other = []
        v_list_my = []
        pr_list = []
        refuse_to_version_id = ''
        for r in records.workflow_ids:
            if r.name == node_state and r.version_id == first_refuse_id:
                if r.user_id.id == self._uid:
                    v_list_my.append({
                        'type': r.type,
                        'refuse_to': refuse_to,
                        'name': r.name,
                        'model_id': r.model_id.id,
                        'res_id': r.res_id,
                        'create_id': r.create_id.id,
                        'start_date': t,
                        'user_id': r.user_id.id,
                        'end_date': t,
                        'note': message,
                        'state': '拒绝',
                        'accredit': r.accredit,
                        'sequence': 3,
                        'res_record_name': r.res_record_name,
                        'version_id': False
                    })
                else:
                    v_list_other.append({
                        'type': r.type,
                        'name': r.name,
                        'refuse_to': refuse_to,
                        'model_id': r.model_id.id,
                        'res_id': r.res_id,
                        'create_id': r.create_id.id,
                        'start_date': t,
                        'user_id': r.user_id.id,
                        'end_date': t,
                        'note': '由 %s 拒绝' % self.env.user.name,
                        'state': '拒绝',
                        'accredit': r.accredit,
                        'sequence': 3,
                        'res_record_name': r.res_record_name,
                        'version_id': False
                    })
            if r.name == refuse_to:
                if not refuse_to_version_id:
                    refuse_to_version_id = r.version_id
                if r.version_id != refuse_to_version_id:
                    break
                pr_list.append({
                    'name': self._context.get('to_state') + '---->' + refuse_to,
                    'res_id': records.id,
                    'res_model': records._name,
                    'user_id': r.user_id.id,
                })
        new_flows = self.create(v_list_other + v_list_my)
        # 在处理拒绝后把version_id刷成当前拒绝后的id
        if new_flows:
            new_flows.write({'version_id': new_flows.ids[-1]})

        # 处理拒绝后的节点的人员
        # for w in records.workflow_ids:
        #     if w.name == refuse_to and w.version_id == first_refuse_id:
        #         pr_list.append({
        #             'name': self._context.get('to_state') + '---->' + refuse_to,
        #             'res_id': records.id,
        #             'res_model': records._name,
        #             'user_id': w.user_id.id,
        #         })
        self.env['hd.personnel.process.record'].sudo().create(pr_list)
        return True

    def create_workflow_refuse(self, records, type='汇签', message='同意', state_name='', state_next_name='', workflow_users_ids=[], jump_workflows=[], depend_state='state'):
        """
        创建下级用户工作流
        :param records:
        :param content:
        :return:
        """
        records_model = self.env['ir.model'].sudo().search([('model', '=', records._name)], limit=1)
        # 需要处理并签一个同意一个要拒绝的情况
        first_version_id = records.workflow_ids[0].version_id
        refuse_to = records.workflow_ids[0].refuse_to if records.workflow_ids[0].refuse_to else records.workflow_ids.filtered_domain([('refuse_to', '!=', False), ('version_id', '=', first_version_id)])[0].refuse_to
        other_version_id = ''
        now = datetime.now()
        v_list = []
        execute_node_finish = True
        workflow_type_count = 0
        pick_times = 0
        for r in records.workflow_ids.filtered_domain([('state', '!=', '取回'), ('name', '=', refuse_to)]):
            if pick_times == 0:
                other_version_id = r.version_id
            if other_version_id != r.version_id:
                break
            if r.type == '汇签':
                v_list.append({
                        'type': r.type,
                        'name': r.name,
                        'model_id': records_model.id,
                        'res_id': records.id,
                        'start_date': now,
                        'user_id': r.user_id.id,
                        'end_date': now,
                        'note': message if r.user_id.id == self._uid else ('由 %s 汇签' % self.env.user.name),
                        'state': '同意',
                        'accredit': r.accredit,
                        'sequence': 3,
                        'res_record_name': records.name
                })
                workflow_type_count = 1
            elif r.type == '并签' or r.type == '串签':
                execute_node_finish = False
                myself = (r.user_id.id == self._uid)
                v_list.append({
                        'type': r.type,
                        'name': r.name,
                        'model_id': records_model.id,
                        'res_id': records.id,
                        # 'create_id': r.user_id.id,
                        'start_date': now,
                        'user_id': r.user_id.id,
                        'end_date': now if myself else None,
                        'accredit': r.accredit,
                        'note': message if myself else '',
                        'state': '同意' if myself else '等待审批',
                        'sequence': 3,
                        'res_record_name': records.name
                })
                self.env['hd.workflow.together'].create_workflow(records, type, message, state_next_name,
                                                                   workflow_users_ids)
                workflow_type_count += 1
            pick_times += 1
        if workflow_type_count == 1:
                execute_node_finish = True
                records.write({depend_state: state_next_name})
                pr_list = []
                for workflow_users_id in workflow_users_ids:
                    v_list.append({
                            'type': type,
                            'name': state_next_name,
                            'model_id': records_model.id,
                            'res_id': records.id,
                            # 'create_id': r.user_id.id,
                            'start_date': now,
                            'user_id': workflow_users_id,
                            'state': '等待审批',
                            # 'accredit': r.accredit,
                            'sequence': 4,
                            'res_record_name': records.name
                    })
                    pr_list.append({
                        'name': state_name + '---->' + state_next_name,
                        'res_model': records._name,
                        'res_id': records.id,
                        'user_id': workflow_users_id,
                    })
                self.env['hd.personnel.process.record'].sudo().create(pr_list)
        else:
            self.env['hd.personnel.process.record'].sudo().search([('res_model', '=', records._name),
                                                                     ('res_id', '=', records.id),
                                                                     ('valid', '=', '有效'), ('user_id', '=', self._uid)]).write({'valid': '无效'})
        self.create(v_list)
        return execute_node_finish

    def create_workflow_ok(self, records, type='汇签', message='同意', state_name='', workflow_users_ids=[], jump_workflows=[], depend_state='state'):
        """
        创建下级用户工作流
        :param records:
        :param content:
        :return:
        """
        records_model = self.env['ir.model'].sudo().search([('model', '=', records._name)], limit=1)
        now = datetime.now()
        v_list = []
        if records.workflow_ids and records.workflow_ids[0].state == '等待提交':
            records.workflow_ids = [(1, records.workflow_ids[0].id, {'start_date': now,
                                               'end_date': now,
                                               'note': message,
                                               'state': '已提交'
                                               })]
        else:
            v_list.append({
            'type': '汇签',
            'name': '新建',
            'model_id': records_model.id,
            'res_id': records.id,
            'create_id': self._uid,
            'start_date': now,
            'user_id': self._uid,
            'end_date': now,
            'note': message or '同意',
            'state': '已提交',
            'sequence': 1,
            'res_record_name': records.name
        })

        v_list = v_list + jump_workflows
        pr_list = []
        for user in workflow_users_ids:
            v_list.append({
                'type': type,
                'name': state_name,
                'model_id': records_model.id,
                'res_id': records.id,
                'create_id': self._uid,
                'start_date': now,
                'user_id': user,
                'state': '等待审批',
                'accredit': self._context.get('shouquan_dict').get(user) or '无',
                'sequence': 2,
                'res_record_name': records.name
            })
            pr_list.append({
                'name':  '新建' + '---->' + state_name,
                'res_model': records._name,
                'res_id': records.id,
                'user_id': user,
            })
        self.create(v_list)
        self.env['hd.personnel.process.record'].sudo().create(pr_list)
        records.write({depend_state: state_name})