from odoo import models, fields


class ChownBanTransientModel(models.TransientModel):
    _name = 'hd.chown.ban'
    _description = '授权选择人员'

    name = fields.Char('名称')
    ban_person = fields.Many2one('hr.employee', string='授权人员')

    def button_shouquan(self):
        ban_person = self.ban_person
        if self._context.get('parent_id'):
            r = self.env['hd.chown.details'].sudo().search([('parent_id', '=', self._context.get('parent_id'))])
            r.write({
                'chowner': ban_person.id
            })


