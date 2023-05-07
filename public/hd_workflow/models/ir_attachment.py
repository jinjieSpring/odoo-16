from odoo import models


class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    def btn_download_file(self):
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s?download=1' % self.id
        }
