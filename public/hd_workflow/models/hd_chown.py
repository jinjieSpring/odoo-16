# -*- coding: utf-8 -*-
from odoo import models, fields, api
from datetime import datetime, time, timedelta
from dateutil.relativedelta import relativedelta
from odoo.exceptions import UserError


class HdChown(models.Model):
    _name = "hd.chown"
    _description = '审批授权'
    name = fields.Char(string="标题", compute='_compute_complete_name', store=True)
    owner = fields.Many2one('hr.employee', string='授权人', default=lambda self: self.env['hr.employee'].search([('user_id','=', self.env.user.id)]))
    change_start = fields.Datetime(string="授权开始时间", required=1)
    change_end = fields.Datetime(string="授权结束时间", required=1)
    change_reason = fields.Text(string="授权原因")
    type = fields.Selection([('有效', '有效'), ('无效', '无效')], string="状态", default="有效", required=1)
    chown_details = fields.One2many('hd.chown.details', 'parent_id', string="授权明细")

    @api.depends('owner')
    def _compute_complete_name(self):
        for group in self:
            group.name = group.owner.name + "的授权单"

    @api.model
    def default_get(self, fields_list):
        rslt = super(HdChown, self).default_get(fields_list)
        rslt['change_start'] = datetime.combine(fields.Date.today(), time(0, 0, 0))
        rslt['change_end'] = datetime.combine(fields.Date.today() + relativedelta(days=1), time(0, 0, 0))
        return rslt

    def button_state(self):
        if self.type == '无效':
            raise UserError('无效状态下无法操作!')
        # self.chown_details.unlink()
        model_names = self.env['hd.workflow'].sudo().read_group([('res_model',
                                                                  'not in',
                                                                  ['supervise.subject', 'hd.rewards.punishment', 'hd.month.performance'])],
                                                                fields=['res_model'],
                                                                groupby=['res_model'])
        for m in model_names:
            if not (self.chown_details and self.chown_details.filtered(lambda t: t.desc == m['res_model'])):
                values = {
                    'name': self.env['ir.model'].sudo().search([('model', '=', m['res_model'])]).name,
                    'desc': m['res_model'],
                    'parent_id': self.id
                }
                self.env['hd.chown.details'].sudo().create(values)
        return True

    def button_shouquan(self):
        if not self.chown_details:
            raise UserError('请先生成明细!')
        if self.type == '无效':
            raise UserError('无效状态下无法操作!')
        return {
            'name': '请选择授权人员',
            'type': 'ir.actions.act_window',
            'res_model': 'hd.chown.ban',
            "views": [[False, "form"]],
            'target': 'new',
            # 'res_id': create_person.id,
            'context': {'create': False, 'parent_id': self.id}
        }

    @api.model
    def change_type(self):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        records = self.sudo().search([('change_end', '<', now)])
        if records:
            records.write({
                'type': '无效'
            })

    @api.model_create_multi
    def create(self, vals_list):
        # 先处理时间应该要显示多加8小时
        start_records = self.search([('change_start', '<=', vals_list['change_start']),
                                     ('change_end', '>=', vals_list['change_start']),
                                     ('type', '=', '有效')])
        if start_records:
            beijing_time = (datetime.strptime(vals_list['change_start'], '%Y-%m-%d %H:%M:%S') + timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S")
            raise UserError('授权开始时间:' + beijing_time + ",该时间有重叠!")
        end_records = self.search([('change_start', '<=', vals_list['change_end']),
                                   ('change_end', '>=', vals_list['change_end']),
                                   ('type', '=', '有效')])
        if end_records:
            beijing_time = (datetime.strptime(vals_list['change_end'], '%Y-%m-%d %H:%M:%S') + timedelta(
                hours=8)).strftime("%Y-%m-%d %H:%M:%S")
            raise UserError('授权结束时间:' + beijing_time + ",该时间有重叠!")
        return super(HdChown, self).create(vals_list)


class HdChownDetails(models.Model):
    _name = "hd.chown.details"
    _description = '审批授权明细'

    name = fields.Char(string="模块名")
    desc = fields.Char(string="程序名")
    chowner = fields.Many2one('hr.employee', string='被授权人')
    parent_id = fields.Many2one('hd.chown', string='审批授权')
