# -*- coding: utf-8 -*-
from odoo import models, fields, api


class RepairApplication(models.Model):
    _name = 'repair.application'
    _description = '维修申请'
    _inherit = ['hd.workflow.mixin']

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
    state = fields.Selection(selection=lambda self: self._get_state(), string='状态', default='新建')

    @api.model
    def _get_state(self):
        return super()._default_states() + [('新建', '新建'),
                          ('综合接口人', '综合接口人'),
                          ('综合管理部负责人', '综合管理部负责人'),
                          ('核二院接口人', '核二院接口人'),
                          ('物业接口人', '物业接口人'),
                          ('申请人', '申请人'),
                          ('已审核', '已审核')]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name', 'New') == 'new':
                vals['name'] = self.env['ir.sequence'].next_by_code('repair.application')
        result = super(RepairApplication, self).create(vals_list)
        return result

    def action_confirm(self):
        return super(RepairApplication, self).action_confirm()