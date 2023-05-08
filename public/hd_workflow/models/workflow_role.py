from odoo import fields, models


class HdWorkflowRole(models.Model):
    _name = 'hd.workflow.role'
    _description = '工作流角色'

    _sql_constraints = [
        ('code_uniq', 'unique (code)', '角色代码已存在')
    ]

    name = fields.Char(string='角色名称', required=True)
    code = fields.Char(string='角色代码', required=True)
    users_ids = fields.Many2many('res.users', string='人员')
    remarks = fields.Text(string='备注', default='无')
