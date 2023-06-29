from odoo import api, fields, models
from odoo.exceptions import UserError
from .hd_workflow_mixin import WORKFLOW_STATE


class IrProcess(models.Model,):
    _name = "ir.process"
    _description = "发启流程"

    name = fields.Char(string='流程名称')
    model_id = fields.Many2one('ir.model', string='模型对象')
    model = fields.Char(related='model_id.model', string='模型对象名称', store=True)
    active = fields.Boolean(default=True, string='是否有效')
    process_ids = fields.One2many('ir.process.line', 'process_id', string='节点明细')
    depend_state = fields.Char(string='依赖字段', default='state')
    note = fields.Text(string='备注', default='无')

    @api.onchange('model_id')
    def onchange_model_id(self):
        values = {}
        if self.model_id:
            values['name'] = self.model_id.name + '的流程'
        self.update(values)

    def button_state(self):
        """
        计算出对象状态下有多少个状态，并安顺序生成好
        用户再配置好状态间的关系
        :return:
        """
        # 判断根据哪个state字段生成
        if hasattr(self.pool.models[self.model_id.model], self.depend_state):
            func_selection = getattr(self.pool.models[self.model_id.model], self.depend_state).selection
        else:
            raise UserError(f'模型:{self.model_id.model}里面没有{self.depend_state}字段')
        self.process_ids.unlink()
        sequence = 1
        selection = func_selection(self.env[self.model_id.model])[len(WORKFLOW_STATE):]
        for line in selection:
            self.env['ir.process.line'].create({
                'sequence': sequence,
                'process_id': self.id,
                'name': line[0],
                'can_back': True if sequence == 2 else False,
                #'can_back': False if line[0] == '新建' or len(selection) == sequence else True,
                'is_stop': True if len(selection) == sequence else False
            })
            sequence = sequence + 1


class IrProcessLine(models.Model):
    _name = "ir.process.line"
    _description = "流程明细"
    _order = 'sequence asc'

    # button_name 和 domain 未使用,由workflow_minln.py的方法替代了。
    process_id = fields.Many2one('ir.process', string='明细', required=True, ondelete='cascade', index=True)
    name = fields.Char(string='节点名称')
    button_name = fields.Text(string='Custom Python Code', default='model.custom_get_res_users()', help="配合自定义使用写成方法。")
    sequence = fields.Integer(string='排序', default=1)
    type = fields.Selection([('自定义', '自定义'), ('固定审核人', '固定审核人'), ('角色组', '角色组'), ('节点审核人', '节点审核人'), ('权限组', '权限组')], string='审批人获取方式', default='自定义')
    is_stop = fields.Boolean(default=False, string='停止工作流')
    is_fixed = fields.Boolean(default=False, string='编辑审核人')
    domain = fields.Text(string='下拉选人domain', default='model.custom_res_users_domain()')
    approve_type = fields.Selection([('汇签', '汇签'), ('串签', '串签'), ('并签', '并签')], string='审批方式', default='汇签')
    context = fields.Text(string='上下文', help='用于记录上下文信息与客户端同步')
    groups_ids = fields.Many2many('res.groups', 'ir_process_line_res_groups_rel', 'process_id', 'group_id', string='权限组')
    users_ids = fields.Many2many('res.users', 'ir_process_line_res_users_rel', 'process_id', 'user_id', string='固定审核人')
    workflow_role_ids = fields.Many2many('hd.workflow.role', 'ir_process_line_hd_workflow_role_rel', 'process_id', 'role_id', string='角色组')
    before_ids = fields.Many2many('ir.process.line', 'ir_process_line_approve_rel', 'process_id', 'before_process_id', string='节点审核人')
    is_jump = fields.Boolean(default=False, string='是否跳转')
    jump_code = fields.Text(string='Jump Python Code', default='model.jump_condition()')
    jump_record_show = fields.Boolean(string='显示跳过记录', default=True)
    can_back = fields.Boolean(string='允许取回', default=True)
