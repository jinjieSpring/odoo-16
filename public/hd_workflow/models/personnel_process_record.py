from odoo import api, fields, models


class PersonnelProcessRecord(models.Model):
    _name = "hd.personnel.process.record"
    _description = "人员过程记录"
    _log_access = False

    name = fields.Char(string='过程', help='''新建---->新建''')
    model_id = fields.Many2one('ir.model', string='模型对象')
    res_model = fields.Char(string='对象程序名称', related='model_id.model', store=True, index=True)
    res_id = fields.Integer(string='记录ID', index=True, group_operator=False)
    user_id = fields.Many2one('res.users', string='人员')
    valid = fields.Boolean(string='有效性', default=True, index=True)

    @api.model_create_multi
    def create(self, val_list):
        create_results = super(PersonnelProcessRecord, self).create(val_list)
        notifications = [[r.user_id.partner_id, 'personnel.process.record/updated', {'activity_created': True}] for r in create_results]
        self.env['bus.bus']._sendmany(notifications)
        return create_results

    def write(self, vals):
        notifications = [[r.user_id.partner_id, 'personnel.process.record/updated', {'activity_deleted': True}] for r in self]
        self.env['bus.bus']._sendmany(notifications)
        return super(PersonnelProcessRecord, self).write(vals)

    def unlink(self):
        notifications = [[r.user_id.partner_id, 'personnel.process.record/updated', {'activity_deleted': True}] for r in self]
        self.env['bus.bus']._sendmany(notifications)
        return super(PersonnelProcessRecord, self).unlink()