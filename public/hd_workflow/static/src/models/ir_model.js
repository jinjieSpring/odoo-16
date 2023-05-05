/** @odoo-module **/

import { registerPatch } from '@mail/model/model_core';
import { attr, one } from '@mail/model/model_field';

registerPatch({
    name: 'ir.model',
    fields: {
        /**
         * Determines the name of the views that are available for this model.
         */
        todoGroup: one('TodoGroup', {
            inverse: 'irModel',
        })
    },
});
