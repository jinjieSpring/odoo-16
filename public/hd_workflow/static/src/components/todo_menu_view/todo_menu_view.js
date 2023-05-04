/** @odoo-module **/

import { useComponentToModel } from "@mail/component_hooks/use_component_to_model";
import { registerMessagingComponent } from "@mail/utils/messaging_component";

const { Component } = owl;

export class TodoMenuView extends Component {
    /**
     * @override
     */
     setup() {
        super.setup();
    }
    /**
     * @returns {TodoMenuView}
     */
    // get todoMenuView() {
    //     return this.props.record;
    // }
}

Object.assign(TodoMenuView, {
    props: { record: Object },
    template: 'hd_workflow.TodoMenuView',
});

registerMessagingComponent(TodoMenuView);
