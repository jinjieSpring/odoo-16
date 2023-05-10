from odoo import models
import ast
import json
from odoo.tools import str2bool
from odoo.addons.base.models.ir_ui_view import NameManager, transfer_modifiers_to_node


def transfer_node_to_modifiers(node, modifiers, context=None):
    # Don't deal with groups, it is done by check_group().
    attrs = node.attrib.pop('attrs', None)
    if attrs:
        attrs = node.get('attrs').strip()
        if ', uid' in attrs:
            user_id = str(context.get('uid', 1))
            user_id = ', ' + user_id
            attrs = attrs.replace(', uid', user_id)
        modifiers.update(ast.literal_eval(attrs.strip()))
        for a in ('invisible', 'readonly', 'required'):
            if a in modifiers and isinstance(modifiers[a], int):
                modifiers[a] = bool(modifiers[a])

    states = node.attrib.pop('states', None)
    if states:
        states = states.split(',')
        if 'invisible' in modifiers and isinstance(modifiers['invisible'], list):
            # TODO combine with AND or OR, use implicit AND for now.
            modifiers['invisible'].append((node.get('depend_state') if node.get('depend_state') else 'state', 'not in', node.get('states').split(',')))
        else:
            modifiers['invisible'] = [(node.get('depend_state') if node.get('depend_state') else 'state', 'not in', node.get('states').split(','))]

    context_dependent_modifiers = {}
    for attr in ('invisible', 'readonly', 'required'):
        value_str = node.attrib.pop(attr, None)
        if value_str:

            if (attr == 'invisible'
                    and any(parent.tag == 'tree' for parent in node.iterancestors())
                    and not any(parent.tag == 'header' for parent in node.iterancestors())):
                # Invisible in a tree view has a specific meaning, make it a
                # new key in the modifiers attribute.
                attr = 'column_invisible'

            # TODO: for invisible="context.get('...')", delegate to the web client.
            try:
                # most (~95%) elements are 1/True/0/False
                value = str2bool(value_str)
            except ValueError:
                # if str2bool fails, it means it's something else than 1/True/0/False,
                # meaning most-likely `context.get('...')`,
                # which should be evaluated after retrieving the view arch from the cache
                context_dependent_modifiers[attr] = value_str
                continue

            if value or (attr not in modifiers or not isinstance(modifiers[attr], list)):
                # Don't set the attribute to False if a dynamic value was
                # provided (i.e. a domain from attrs or states).
                modifiers[attr] = value

    if context_dependent_modifiers:
        node.set('context-dependent-modifiers', json.dumps(context_dependent_modifiers))


class View(models.Model):
    _inherit = 'ir.ui.view'

    def _postprocess_view(self, node, model_name, editable=True, parent_name_manager=None, **options):
        """ Process the given architecture, modifying it in-place to add and
        remove stuff.

        :param self: the optional view to postprocess
        :param node: the combined architecture as an etree
        :param model_name: the view's reference model name
        :param editable: whether the view is considered editable
        :return: the processed architecture's NameManager
        """
        root = node

        if model_name not in self.env:
            self._raise_view_error(_('Model not found: %(model)s', model=model_name), root)
        model = self.env[model_name]

        if self._onchange_able_view(root):
            self._postprocess_on_change(root, model)

        name_manager = NameManager(model, parent=parent_name_manager)

        root_info = {
            'view_type': root.tag,
            'view_editable': editable and self._editable_node(root, name_manager),
            'view_modifiers_from_model': self._modifiers_from_model(root),
            'mobile': options.get('mobile'),
        }

        # use a stack to recursively traverse the tree
        stack = [(root, editable)]
        while stack:
            node, editable = stack.pop()

            # compute default
            tag = node.tag
            had_parent = node.getparent() is not None
            node_info = dict(root_info, modifiers={}, editable=editable and self._editable_node(node, name_manager))

            # tag-specific postprocessing
            postprocessor = getattr(self, f"_postprocess_tag_{tag}", None)
            if postprocessor is not None:
                postprocessor(node, name_manager, node_info)
                if had_parent and node.getparent() is None:
                    # the node has been removed, stop processing here
                    continue

            transfer_node_to_modifiers(node, node_info['modifiers'], self._context)
            transfer_modifiers_to_node(node_info['modifiers'], node)

            # if present, iterate on node_info['children'] instead of node
            for child in reversed(node_info.get('children', node)):
                stack.append((child, node_info['editable']))

        name_manager.update_available_fields()
        root.set('model_access_rights', model._name)

        return name_manager