from odoo import api, fields, models, modules


class PersonnelProcessRecord(models.Model):
    _name = "hd.personnel.process.record"
    _description = "人员过程记录"
    _log_access = False

    name = fields.Char(string='过程', help='''新建---->新建''')
    model_id = fields.Many2one('ir.model', string='模型对象')
    res_model = fields.Char(string='对象程序名称', related='model_id.model', store=True)
    res_id = fields.Integer(string='记录ID', group_operator=False)
    user_id = fields.Many2one('res.users', string='人员')
    valid = fields.Boolean(string='有效性', default=True)
    series_wound = fields.Boolean(string='跳出串签节点', help='''串签用来记录当前人提交的是不是进入下一节点''')

    @api.model
    def workflow_bus_send(self, records, mode):
        notifications = [[r.user_id.partner_id, 'hd.personnel.process.record/updated', {mode: True}] for r in records if r.user_id.partner_id]
        # print(notifications)
        self.env['bus.bus']._sendmany(notifications)

    @api.model_create_multi
    def create(self, val_list):
        if self._context.get('active_model') and self._context.get('active_id'):
            self.search([('res_id', '=', self._context.get('active_id')),
                         ('res_model', '=', self._context.get('active_model')),
                         ('valid', '=', True)]).with_context(way='create', mode='todo_deleted').write({'valid': False})
        create_results = super(PersonnelProcessRecord, self).create(val_list)
        self.workflow_bus_send(create_results.filtered_domain([('valid', '=', True)]), 'todo_created')
        return create_results

    def write(self, vals):
        """
            write方法只处理create方法中要修改成无效的数据, 不处理直接编辑, 直接编辑要重新点击待办按钮获取
        """
        if self._context.get('way') and self._context.get('mode'):
            self.workflow_bus_send(self, self._context.get('mode'))
        return super(PersonnelProcessRecord, self).write(vals)

    def unlink(self):
        self.workflow_bus_send(self, self.filtered_domain([('valid', '=', True)]), 'todo_deleted')
        return super(PersonnelProcessRecord, self).unlink()

    @api.model
    def systray_get_todoes(self):
        todo_data = self.search([('valid', '=', True), ('user_id', '=', self._uid)])
        user_todos = {}
        # 缓存
        for todo in todo_data:
            ir_model_sudo = todo.model_id.sudo()
            key = todo.res_model
            if user_todos.get(key):
                user_todos[key]['total_count'] = user_todos[key]['total_count'] + 1
                user_todos[key]['todo_count'] = user_todos[key]['todo_count'] + 1
            else:
                module = self.env[key]._original_module
                icon = module and modules.module.get_module_icon(module)
                user_todos[todo['res_model']] = {
                        'id': ir_model_sudo.id,
                        'name': ir_model_sudo.name,
                        'model': key,
                        'type': 'todo',
                        'icon': icon,
                        'total_count': 1,
                        'todo_count': 1
                }
        return list(user_todos.values())
