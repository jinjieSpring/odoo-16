/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";
import { useState, onRendered } from "@odoo/owl";


function getActiveActionsRp(rootNode, record) {
    return {
        type: "view",
        rp_edit: archParseBooleanRp(rootNode.getAttribute("rp_edit"), true, record),
        rp_create: archParseBooleanRp(rootNode.getAttribute("rp_create"), true, record),
        rp_delete: archParseBooleanRp(rootNode.getAttribute("rp_delete"), true, record),
        rp_duplicate: archParseBooleanRp(rootNode.getAttribute("rp_duplicate"), true, record),
    };
}

function archParseBooleanRp(str, trueIfEmpty = false, record) {
    if(str){
        const tokens = py.tokenize(str);
        const tree = py.parse(tokens);
        const expr_eval = py.evaluate(tree, record)
        return py.PY_isTrue(expr_eval)
    }else return trueIfEmpty;
}

// patch(FormController, "form_controller", {
//     defaultProps: {
//         ...FormController.defaultProps,
//         preventEdit: true,
//     }
// });

patch(FormController.prototype, "hd_workflow/views/form",{
    setup() {
        this._super(...arguments);
        this.state = useState({
            rpEdit: true,
            rpCreate: true,
            rpDelete: true,
            rpDuplicate: true,
        });
        onRendered(() => {
            const {rp_edit, rp_create, rp_delete, rp_duplicate} = getActiveActionsRp(this.archInfo.xmlDoc, this.model.root.data)
            this.state.rpEdit = rp_edit;
            this.state.rpCreate = rp_create;
            this.state.rpDelete = rp_delete;
            this.state.rpDuplicate = rp_duplicate;
        });
    },
    getActionMenuItems() {
        const otherActionItems = [];
        if (this.archiveEnabled) {
            if (this.model.root.isActive) {
                otherActionItems.push({
                    key: "archive",
                    description: this.env._t("Archive"),
                    callback: () => {
                        const dialogProps = {
                            body: this.env._t(
                                "Are you sure that you want to archive this record?"
                            ),
                            confirmLabel: this.env._t("Archive"),
                            confirm: () => this.model.root.archive(),
                            cancel: () => {},
                        };
                        this.dialogService.add(ConfirmationDialog, dialogProps);
                    },
                });
            } else {
                otherActionItems.push({
                    key: "unarchive",
                    description: this.env._t("Unarchive"),
                    callback: () => this.model.root.unarchive(),
                });
            }
        }
        if (this.archInfo.activeActions.create && this.archInfo.activeActions.duplicate && this.state.rpDuplicate) {
            otherActionItems.push({
                key: "duplicate",
                description: this.env._t("Duplicate"),
                callback: () => this.duplicateRecord(),
            });
        }
        if (this.archInfo.activeActions.delete && !this.model.root.isVirtual && this.state.rpDelete) {
            otherActionItems.push({
                key: "delete",
                description: this.env._t("Delete"),
                callback: () => this.deleteRecord(),
                skipSave: true,
            });
        }
        return Object.assign({}, this.props.info.actionMenus, { other: otherActionItems });
    }
})








