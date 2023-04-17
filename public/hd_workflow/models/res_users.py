from odoo import fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    psignature = fields.Binary(string="个人签名", groups='base.group_user')

    @property
    def SELF_WRITEABLE_FIELDS(self):
        """ The list of fields a user can write on their own user record.
        In order to add fields, please override this property on model extensions.
        """
        return super().SELF_WRITEABLE_FIELDS + ['work_email', 'mobile_phone', 'work_phone', 'psignature']
