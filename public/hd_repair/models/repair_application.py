# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError
from odoo.workflow_mixIn import WorkFlowMixln, WORKFLOW_STATE


class RepairApplication(models.Model, WorkFlowMixln):
    _name = 'repair.application'
    _description = '维修申请'

    name = fields.Char(string='编号', default='New', readonly=True)
    subject = fields.Char(string='标题', help="用于之后看板等显示关键信息,name字段无法满足")
    apply_user = fields.Many2one('hr.employee', string="申请人", default=lambda self: self.env['hr.employee'].search([('user_id', '=', self.env.user.id)]).id, required=True)
    user_dept = fields.Many2one('hr.department', string='部门', related='apply_user.department_id')
    user_phone = fields.Char(string='联系电话')
    area = fields.Selection([('办公区', '办公区'), ('生活区', '生活区')], '维修区域', default='办公区', required=True)
    location = fields.Char(string='维修地点', required=True)
    specification = fields.Text(string='维修说明', required=True)
    expected_time = fields.Datetime(string='期望维修时间', default=fields.Datetime.now)
    format_year_test_date = fields.Integer(string='只选择年', help="format_year前缀是针对list和form把inter显示成年，要配合widet='year_datepick'使用")
    state = fields.Selection(selection=WORKFLOW_STATE + [
        ('新建', '新建'),
        ('综合接口人', '综合接口人'),
        ('综合管理部负责人', '综合管理部负责人'),
        ('核二院接口人', '核二院接口人'),
        ('物业接口人', '物业接口人'),
        ('申请人', '申请人'),
        ('已审核', '已审核'),
    ], string='状态', default='新建')
    #:::工作流
    # res_id 记录ID  res_model 对象名称
    workflow_ids = fields.One2many('hd.workflow', 'res_id', domain=lambda self: [('res_model', '=', self._name), ('is_show', '=', True)], string='审批记录')
    workflow_look = fields.Boolean(string='审核按钮是否可见', default=False, compute='_compute_workflow_look', help='True')
    depend_state = fields.Char(string='依赖状态', compute='_compute_depend_state', store=True, default='state')
    finally_show_state_desc = fields.Char(string='最新状态', default='新建')
    ir_process_id = fields.Many2one('ir.process', string='流程')
    line_buttons = fields.Json(string='button属性', compute="_compute_line_buttons", store=True, copy=True, readonly=False)
    attachment_ids = fields.One2many('ir.attachment', 'res_id', domain=lambda self: [('res_model', '=', self._name)], string='附件')
    attachment_number = fields.Integer(compute='_compute_attachment_number', string='附件数量')

    def default_get(self, fields_list):
        result = super(RepairApplication, self).default_get(fields_list)
        result['create_uid'] = self._uid
        result['ir_process_id'] = self.env['ir.process'].search([('model', '=', self._name), ('active', '=', True)], order="id desc", limit=1).id
        return result

    @api.model
    def create(self, vals):
        if not vals.get('name', 'New') == 'new':
            vals['name'] = self.env['ir.sequence'].get('repair.application')
        result = super(RepairApplication, self).create(vals)
        self.create_workflow_new(result)
        return result

    def unlink(self):
        for order in self:
            if len(order.workflow_ids) > 1:
                raise UserError('已提交的单子无法删除!')
            else:
                order.workflow_ids.unlink()
                self.env['hd.personnel.process.record'].sudo().search(
                    [('res_model', '=', self._name), ('res_id', '=', order.id)]).unlink()
        return super(RepairApplication, self).unlink()

    @api.model
    def search_read(self, domain=None, fields=None, offset=0, limit=None, order=None):
        logid = self.env.user.id
        do_type = self._context.get('do_type')
        if do_type == 'shenqing':
            domain.append(('create_uid', '=', logid))
        elif do_type == 'yiban':
            domain.append(('id', 'in', [s.res_id for s in self.env['hd.personnel.process.record'].sudo().search([('user_id', '=', logid),
                                                                                                                   ('res_model', '=', self._name),
                                                                                                                   ('valid', '=', '无效')])]))
        elif do_type == 'all':
            pass
        else:
            domain.append(('id', 'in', [s.res_id for s in self.env['hd.personnel.process.record'].sudo().search([('valid', '=', '有效'),
                                                                            ('res_model', '=', self._name),
                                                                            ('user_id', '=', logid)])]))
        return super(RepairApplication, self).search_read(domain=domain, fields=fields, offset=offset,
                                                                     limit=limit, order=order)

    def action_confirm(self):
        # if not self.user_phone:
        #     raise UserError('电话没有填入!')
        return super(RepairApplication, self).action_confirm()

    # def get_node_users(self, state):
    #     """
    #          该方法直接返回res_user为id的人员数组,形式[(0, 0, {'user_id':2})], 其中state为提交后的节点名称，即A→B的过程中的B
    #      """
    #
    #     if state == '综合接口人':
    #         if self.area == '生活区':
    #             return [d.id for d in self.env['hd.role'].sudo().search([('name', '=', '维修申请-生活区接口人')], limit=1).maintain_ids]
    #         elif self.area == '办公区':
    #             return [d.id for d in
    #                     self.env['hd.role'].sudo().search([('name', '=', '维修申请-办公区接口人')], limit=1).maintain_ids]


    # 这是最常用的缓存装饰器。您需要传递方法输出所依赖的参数名。下面是一个带有ormcache装饰器的示例方法:
    #
    # @tools.ormcache('mode')
    # def fetch_mode_data(self, mode):
    #     # some calculations
    #     return result
    #
    # 当我们首次调用该函数的时候，将会返回计算值。ormcache将会存储mode的值及result的值。如果我们再次调用该函数，且mode的值为之前存在的值时，将直接返回result的值。
    #
    # 有时，我们的函数依赖于环境属性。比如:

    # @tools.ormcache('self.env.uid', 'mode')
    # def fetch_data(self, mode):
    #     # some calculations
    #     return result
    # 该函数将根据当前用户及mode的值存储result的值。


    # @api.model
    # @tools.ormcache('area', mode='read')
    # def _check_vies(self, area):
    #     print(area)
    #     # Store the VIES result in the cache. In case an exception is raised during the request
    #     # (e.g. service unavailable), the fallback on simple_vat_check is not kept in cache.
    #     return area