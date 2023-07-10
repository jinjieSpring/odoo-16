# -*- coding: utf-8 -*-
{
    'name': '维修申请',
    'summary': '报送给物业进行维修(生活区、办公区)',
    'author': 'Jinjie',
    'category': '公共/公共',
    'website': '',
    'depends' : ['base', 'hr', 'hd_workflow'],
    'version': '2.0',
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/sequence.xml',
        'views/repair_application.xml',
        'views/menu.xml'
    ],
    'assets': {
        # 'web.report_assets_common': [
        #     'amos_workflow/static/src/css/pdf_table.css',
        # ]
    },
    'installable': True,
    'application': True,
    'auto_install': False,
    'description': """""",
    'license': 'LGPL-3'
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
