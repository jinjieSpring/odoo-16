/** @odoo-module **/

import { TodoMenuContainer } from '../components/todo_menu_container/todo_menu_container';
import { registry } from '@web/core/registry';
const systrayRegistry = registry.category('systray');

systrayRegistry.add('hd_workflow.TodoMenuContainer', { Component: TodoMenuContainer }, { sequence: 21 });
