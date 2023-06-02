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
    code_function = fields.Text(string='方法代码')
    remarks = fields.Text(string='备注', default='人员有数据则优先使用，无数据则使用代码获取人员')
