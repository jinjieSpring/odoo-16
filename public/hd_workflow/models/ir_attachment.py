from odoo import models, api
import base64


class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    @api.model_create_multi
    def create(self, vals_list):
        record_tuple_set = set()

        # remove computed field depending of datas
        if not self._context.get('big_attachment', False):
            vals_list = [{
                key: value
                for key, value
                in vals.items()
                if key not in ('file_size', 'checksum', 'store_fname')
            } for vals in vals_list]

        for values in vals_list:
            values = self._check_contents(values)
            raw, datas = values.pop('raw', None), values.pop('datas', None)
            if raw or datas:
                if isinstance(raw, str):
                    # b64decode handles str input but raw needs explicit encoding
                    raw = raw.encode()
                values.update(self._get_datas_related_values(
                    raw or base64.b64decode(datas or b''),
                    values['mimetype']
                ))

            # 'check()' only uses res_model and res_id from values, and make an exists.
            # We can group the values by model, res_id to make only one query when
            # creating multiple attachments on a single record.
            record_tuple = (values.get('res_model'), values.get('res_id'))
            record_tuple_set.add(record_tuple)

        # don't use possible contextual recordset for check, see commit for details
        Attachments = self.browse()
        for res_model, res_id in record_tuple_set:
            Attachments.check('create', values={'res_model': res_model, 'res_id': res_id})
        return models.BaseModel.create(self, vals_list)

    def btn_download_file(self):
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s?download=1' % self.id
        }
