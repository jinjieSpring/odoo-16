/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { Field } from "@web/views/fields/field";
import { evaluateExpr } from "@web/core/py_js/py";
import { evalDomain } from "@web/views/utils";

patch(Field.prototype, 'hd_workflow/models/field', {
    get fieldComponentProps() {
        const record = this.props.record;
        const evalContext = record.evalContext;
        const field = record.fields[this.props.name];
        const fieldInfo = this.props.fieldInfo;

        const modifiers = fieldInfo.modifiers || {};
        let readonlyFromModifiers = evalDomain(modifiers.readonly, evalContext);
        if(record.data.hasOwnProperty('workflow_look')){
            if (!record.data['workflow_look']){
                readonlyFromModifiers = true
            }
        }else {
            readonlyFromModifiers = evalDomain(modifiers.readonly, record.evalContext);
        }
        // Decoration props
        const decorationMap = {};
        const { decorations } = fieldInfo;
        for (const decoName in decorations) {
            const value = evaluateExpr(decorations[decoName], evalContext);
            decorationMap[decoName] = value;
        }

        let propsFromAttrs = fieldInfo.propsFromAttrs;
        if (this.props.attrs) {
            const extractProps = this.FieldComponent.extractProps || (() => ({}));
            propsFromAttrs = extractProps({
                field,
                attrs: {
                    ...this.props.attrs,
                    options: evaluateExpr(this.props.attrs.options || "{}"),
                },
            });
        }

        const props = { ...this.props };
        delete props.style;
        delete props.class;
        delete props.showTooltip;
        delete props.fieldInfo;
        delete props.attrs;

        return {
            ...fieldInfo.props,
            update: async (value, options = {}) => {
                const { save } = Object.assign({ save: false }, options);
                await record.update({ [this.props.name]: value });
                if (record.selected && record.model.multiEdit) {
                    return;
                }
                const rootRecord =
                    record.model.root instanceof record.constructor && record.model.root;
                const isInEdition = rootRecord ? rootRecord.isInEdition : record.isInEdition;
                if ((!isInEdition && !readonlyFromModifiers) || save) {
                    // TODO: maybe move this in the model
                    return record.save();
                }
            },
            value: this.props.record.data[this.props.name],
            decorations: decorationMap,
            readonly: !record.isInEdition || readonlyFromModifiers || false,
            ...propsFromAttrs,
            ...props,
            type: field.type,
        };
    }
});
