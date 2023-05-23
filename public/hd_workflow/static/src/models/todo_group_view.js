/** @odoo-module **/

import { registerModel } from '@mail/model/model_core';
import { one } from '@mail/model/model_field';

import session from 'web.session';

registerModel({
    name: 'TodoGroupView',
    recordMethods: {
        /**
         * @param {MouseEvent} ev
         */
        onClick(ev) {
            ev.stopPropagation();
            this.todoMenuViewOwner.update({ isOpen: false });
            const targetAction = $(ev.currentTarget);
            const actionXmlid = targetAction.data('action_xmlid');
            const context = {'do_type':'daiban'};
            if (actionXmlid) {
                this.env.services.action.doAction(actionXmlid);
            } else {
                let domain = [['activity_ids.user_id', '=', session.uid]];
                if (targetAction.data('domain')) {
                    domain = domain.concat(targetAction.data('domain'));
                }
                this.env.services['action'].doAction(
                    {
                        context,
                        domain,
                        name: targetAction.data('model_name'),
                        res_model: targetAction.data('res_model'),
                        type: 'ir.actions.act_window',
                        views: this.todoGroup.irModel.availableWebViews.map(viewName => [false, viewName]),
                    },
                    {
                        clearBreadcrumbs: true,
                        viewType: 'kanban',
                    },
                );
            }
        },
        /**
         * @param {MouseEvent} ev
         */
        onClickFilterButton(ev) {
            this.todoMenuViewOwner.update({ isOpen: false });
            // fetch the data from the button otherwise fetch the ones from the parent (.o_ActivityMenuView_activityGroup).
            const data = _.extend({}, $(ev.currentTarget).data(), $(ev.target).data());
            const context = {'do_type':'daiban'};
            let domain = [];
            this.env.services['action'].doAction(
                {
                    context,
                    domain,
                    name: data.model_name,
                    res_model: data.res_model,
                    search_view_id: [false],
                    type: 'ir.actions.act_window',
                    views: this.todoGroup.irModel.availableWebViews.map(viewName => [false, viewName]),
                },
                {
                    clearBreadcrumbs: true,
                    viewType: 'kanban',
                },
            );
        },
    },
    fields: {
        todoGroup: one('TodoGroup', {
            identifying: true,
            inverse: 'todoGroupViews',
        }),
        todoMenuViewOwner: one('TodoMenuView', {
            identifying: true,
            inverse: 'todoGroupViews',
        }),
    },
});
