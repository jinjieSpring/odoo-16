/** @odoo-module **/

import { registerModel } from '@mail/model/model_core';
import { attr, many } from '@mail/model/model_field';

import session from 'web.session';

registerModel({
    name: 'TodoMenuView',
    lifecycleHooks: {
        _created() {
            this.fetchData();
            document.addEventListener('click', this._onClickCaptureGlobal, true);
        },
        _willDelete() {
            document.removeEventListener('click', this._onClickCaptureGlobal, true);
        },
    },
    recordMethods: {
        close() {
            this.update({ isOpen: false });
        },
        async fetchData() {
            const data = await this.messaging.rpc({
                model: 'hd.personnel.process.record',
                method: 'systray_get_todoes',
                args: [],
                kwargs: { context: session.user_context },
            });
            this.update({
                todoGroups: data.map(vals => this.messaging.models['TodoGroup'].convertData(vals)),
                extraCount: 0,
            });
        },
        /**
         * @param {MouseEvent} ev
         */
        onClickDropdownToggle(ev) {
            ev.preventDefault();
            if (this.isOpen) {
                this.update({ isOpen: false });
            } else {
                this.update({ isOpen: true });
                this.fetchData();
            }
        },
        /**
         * Closes the menu when clicking outside, if appropriate.
         *
         * @private
         * @param {MouseEvent} ev
         */
        _onClickCaptureGlobal(ev) {
            if (!this.exists()) {
                return;
            }
            if (!this.component || !this.component.root.el) {
                return;
            }
            if (this.component.root.el.contains(ev.target)) {
                return;
            }
            this.close();
        },
    },
    fields: {
        todoGroups: many('TodoGroup', {
            sort: [['smaller-first', 'irModel.id']],
        }),
        todoGroupViews: many('TodoGroupView', {
            compute() {
                return this.todoGroups.map(todoGroup => {
                    return {
                        todoGroup,
                    };
                });
            },
            inverse: 'todoMenuViewOwner',
        }),
        component: attr(),
        counter: attr({
            compute() {
                return this.todoGroups.reduce((total, group) => total + group.total_count, this.extraCount);
            },
        }),
        /**
         * Determines the number of activities that have been added in the
         * system but not yet taken into account in each activity group counter.
         *
         * @deprecated this field should be replaced by directly updating the
         * counter of each group.
         */
        extraCount: attr(),
        isOpen: attr({
            default: false,
        }),
    },
});
