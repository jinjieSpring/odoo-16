/** @odoo-module **/

import { registerModel } from '@mail/model/model_core';
import { attr, many, one } from '@mail/model/model_field';

registerModel({
    name: 'TodoGroup',
    modelMethods: {
        convertData(data) {
            return {
                actions: data.actions,
                domain: data.domain,
                irModel: {
                    iconUrl: data.icon,
                    id: data.id,
                    model: data.model,
                    name: data.name,
                },
                todo_count: data.todo_count,
                total_count: data.total_count,
                type: data.type,
            };
        },
    },
    recordMethods: {
        /**
         * @private
         */
        _onChangeTotalCount() {
            if (this.type === 'todo' && this.total_count === 0 && this.todo_count === 0) {
                this.delete();
            }
        },
    },
    fields: {
        actions: attr(),
        todoGroupViews: many('TodoGroupView', {
            inverse: 'todoGroup',
        }),
        domain: attr(),
        irModel: one('ir.model', {
            identifying: true,
            inverse: 'todoGroup',
        }),
        todo_count: attr({
            default: 0,
        }),
        total_count: attr({
            default: 0,
        }),
        type: attr(),
    },
    onChanges: [
        {
            dependencies: ['total_count', 'type', 'todo_count'],
            methodName: '_onChangeTotalCount',
        },
    ],
});
