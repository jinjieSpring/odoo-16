/** @odoo-module **/

// ensure components are registered beforehand.
import '../todo_menu_view/todo_menu_view';
import { getMessagingComponent } from "@mail/utils/messaging_component";

const { Component } = owl;

export class TodoMenuContainer extends Component {

    /**
     * @override
     */
    setup() {
        super.setup();
    }
}

Object.assign(TodoMenuContainer, {
    components: { TodoMenuView: getMessagingComponent('TodoMenuView') },
    template: 'hd_workflow.TodoMenuContainer',
});
