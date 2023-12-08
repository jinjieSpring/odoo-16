# -*- coding: utf-8 -*-

from odoo.addons.stock.tests.common import TestStockCommon
from odoo.exceptions import ValidationError
from odoo.tests import Form, tagged
from odoo.tools import mute_logger, float_round
from odoo import fields


class TestStockFlow(TestStockCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        decimal_product_uom = cls.env.ref('product.decimal_product_uom')
        decimal_product_uom.digits = 3
        cls.partner_company2 = cls.env['res.partner'].create({
            'name': 'My Company (Chicago)-demo',
            'email': 'chicago@yourcompany.com',
            'company_id': False,
        })
        cls.company = cls.env['res.company'].create({
            'currency_id': cls.env.ref('base.USD').id,
            'partner_id': cls.partner_company2.id,
            'name': 'My Company (Chicago)-demo',
        })

    @mute_logger('odoo.addons.base.models.ir_model', 'odoo.models')
    def test_00_picking_create_and_transfer_quantity(self):
        """ Basic stock operation on incoming and outgoing shipment. """
        LotObj = self.env['stock.lot']
        # ----------------------------------------------------------------------
        # Create incoming shipment of product A, B, C, D
        # ----------------------------------------------------------------------
        #   Product A ( 1 Unit ) , Product C ( 10 Unit )
        #   Product B ( 1 Unit ) , Product D ( 10 Unit )
        #   Product D ( 5 Unit )
        # ----------------------------------------------------------------------

        picking_in = self.PickingObj.create({
            'picking_type_id': self.picking_type_in,
            'location_id': self.supplier_location,
            'state': 'draft',
            'location_dest_id': self.stock_location})
        move_a = self.MoveObj.create({
            'name': self.productA.name,
            'product_id': self.productA.id,
            'product_uom_qty': 1,
            'product_uom': self.productA.uom_id.id,
            'picking_id': picking_in.id,
            'location_id': self.supplier_location,
            'location_dest_id': self.stock_location})
        move_b = self.MoveObj.create({
            'name': self.productB.name,
            'product_id': self.productB.id,
            'product_uom_qty': 1,
            'product_uom': self.productB.uom_id.id,
            'picking_id': picking_in.id,
            'location_id': self.supplier_location,
            'location_dest_id': self.stock_location})
        move_c = self.MoveObj.create({
            'name': self.productC.name,
            'product_id': self.productC.id,
            'product_uom_qty': 10,
            'product_uom': self.productC.uom_id.id,
            'picking_id': picking_in.id,
            'location_id': self.supplier_location,
            'location_dest_id': self.stock_location})
        move_d = self.MoveObj.create({
            'name': self.productD.name,
            'product_id': self.productD.id,
            'product_uom_qty': 10,
            'product_uom': self.productD.uom_id.id,
            'picking_id': picking_in.id,
            'location_id': self.supplier_location,
            'location_dest_id': self.stock_location})
        self.MoveObj.create({
            'name': self.productD.name,
            'product_id': self.productD.id,
            'product_uom_qty': 5,
            'product_uom': self.productD.uom_id.id,
            'picking_id': picking_in.id,
            'location_id': self.supplier_location,
            'location_dest_id': self.stock_location})

        # Check incoming shipment move lines state.
        for move in picking_in.move_ids:
            self.assertEqual(move.state, 'draft', 'Wrong state of move line.')
        # Confirm incoming shipment.
        picking_in.action_confirm()
        # Check incoming shipment move lines state.
        for move in picking_in.move_ids:
            self.assertEqual(move.state, 'assigned', 'Wrong state of move line.')

        # ----------------------------------------------------------------------
        # Replace pack operation of incoming shipments.
        # ----------------------------------------------------------------------
        picking_in.action_assign()
        move_a.move_line_ids.quantity = 4
        move_b.move_line_ids.quantity = 5
        move_c.move_line_ids.quantity = 5
        move_d.move_line_ids.quantity = 5
        (move_a | move_b | move_c | move_d).picked = True
        lot2_productC = LotObj.create({'name': 'C Lot 2', 'product_id': self.productC.id, 'company_id': self.env.company.id})
        self.StockPackObj.create({
            'product_id': self.productC.id,
            'quantity': 2,
            'product_uom_id': self.productC.uom_id.id,
            'location_id': self.supplier_location,
            'location_dest_id': self.stock_location,
            'move_id': move_c.id,
            'lot_id': lot2_productC.id,
        })
        self.StockPackObj.create({
            'product_id': self.productD.id,
            'quantity': 2,
            'product_uom_id': self.productD.uom_id.id,
            'location_id': self.supplier_location,
            'location_dest_id': self.stock_location,
            'move_id': move_d.id
        })

        # Check incoming shipment total quantity of pack operation
        total_qty = sum(self.StockPackObj.search([('move_id', 'in', picking_in.move_ids.ids)]).mapped('quantity'))
        self.assertEqual(total_qty, 23, 'Wrong quantity in pack operation')

        # Transfer Incoming Shipment.
        picking_in._action_done()

        # ----------------------------------------------------------------------
        # Check state, quantity and total moves of incoming shipment.
        # ----------------------------------------------------------------------

        # Check total no of move lines of incoming shipment. move line e disappear from original picking to go in backorder.
        self.assertEqual(len(picking_in.move_ids), 4, 'Wrong number of move lines.')
        # Check incoming shipment state.
        self.assertEqual(picking_in.state, 'done', 'Incoming shipment state should be done.')
        # Check incoming shipment move lines state.
        for move in picking_in.move_ids:
            self.assertEqual(move.state, 'done', 'Wrong state of move line.')
        # Check product A done quantity must be 3 and 1
        moves = self.MoveObj.search([('product_id', '=', self.productA.id), ('picking_id', '=', picking_in.id)])
        self.assertEqual(moves.quantity, 4.0, 'Wrong move quantity for product A.')
        # Check product B done quantity must be 4 and 1
        moves = self.MoveObj.search([('product_id', '=', self.productB.id), ('picking_id', '=', picking_in.id)])
        self.assertEqual(moves.quantity, 5.0, 'Wrong move quantity for product B.')
        # Check product C done quantity must be 7
        c_done_qty = self.MoveObj.search([('product_id', '=', self.productC.id), ('picking_id', '=', picking_in.id)], limit=1).product_uom_qty
        self.assertEqual(c_done_qty, 7.0, 'Wrong move quantity of product C (%s found instead of 7)' % (c_done_qty))
        # Check product D done quantity must be 7
        d_done_qty = self.MoveObj.search([('product_id', '=', self.productD.id), ('picking_id', '=', picking_in.id)], limit=1).product_uom_qty
        self.assertEqual(d_done_qty, 7.0, 'Wrong move quantity of product D (%s found instead of 7)' % (d_done_qty))

        # ----------------------------------------------------------------------
        # Check Back order of Incoming shipment.
        # ----------------------------------------------------------------------

        # Check back order created or not.
        back_order_in = self.PickingObj.search([('backorder_id', '=', picking_in.id)])
        self.assertEqual(len(back_order_in), 1, 'Back order should be created.')
        # Check total move lines of back order.
        self.assertEqual(len(back_order_in.move_ids), 2, 'Wrong number of move lines.')
        # Check back order should be created with 3 quantity of product C.
        moves = self.MoveObj.search([('product_id', '=', self.productC.id), ('picking_id', '=', back_order_in.id)])
        product_c_qty = [move.product_uom_qty for move in moves]
        self.assertEqual(sum(product_c_qty), 3.0, 'Wrong move quantity of product C (%s found instead of 3)' % (product_c_qty))
        # Check back order should be created with 8 quantity of product D.
        moves = self.MoveObj.search([('product_id', '=', self.productD.id), ('picking_id', '=', back_order_in.id)])
        product_d_qty = [move.product_uom_qty for move in moves]
        self.assertEqual(sum(product_d_qty), 8.0, 'Wrong move quantity of product D (%s found instead of 8)' % (product_d_qty))

        # ======================================================================
        # Create Outgoing shipment with ...
        #   product A ( 10 Unit ) , product B ( 5 Unit )
        #   product C (  3 unit ) , product D ( 10 Unit )
        # ======================================================================

        picking_out = self.PickingObj.create({
            'picking_type_id': self.picking_type_out,
            'location_id': self.stock_location,
            'state': 'draft',
            'location_dest_id': self.customer_location})
        move_cust_a = self.MoveObj.create({
            'name': self.productA.name,
            'product_id': self.productA.id,
            'product_uom_qty': 10,
            'product_uom': self.productA.uom_id.id,
            'picking_id': picking_out.id,
            'location_id': self.stock_location,
            'location_dest_id': self.customer_location})
        move_cust_b = self.MoveObj.create({
            'name': self.productB.name,
            'product_id': self.productB.id,
            'product_uom_qty': 5,
            'product_uom': self.productB.uom_id.id,
            'picking_id': picking_out.id,
            'location_id': self.stock_location,
            'location_dest_id': self.customer_location})
        move_cust_c = self.MoveObj.create({
            'name': self.productC.name,
            'product_id': self.productC.id,
            'product_uom_qty': 3,
            'product_uom': self.productC.uom_id.id,
            'picking_id': picking_out.id,
            'location_id': self.stock_location,
            'location_dest_id': self.customer_location})
        move_cust_d = self.MoveObj.create({
            'name': self.productD.name,
            'product_id': self.productD.id,
            'product_uom_qty': 10,
            'product_uom': self.productD.uom_id.id,
            'picking_id': picking_out.id,
            'location_id': self.stock_location,
            'location_dest_id': self.customer_location})
        # Confirm outgoing shipment.
        picking_out.action_confirm()
        for move in picking_out.move_ids:
            self.assertEqual(move.state, 'confirmed', 'Wrong state of move line.')
        # Product assign to outgoing shipments
        picking_out.action_assign()
        self.assertEqual(move_cust_a.state, 'partially_available', 'Wrong state of move line.')
        self.assertEqual(move_cust_b.state, 'assigned', 'Wrong state of move line.')
        self.assertEqual(move_cust_c.state, 'assigned', 'Wrong state of move line.')
        self.assertEqual(move_cust_d.state, 'partially_available', 'Wrong state of move line.')
        # Check availability for product A
        aval_a_qty = self.MoveObj.search([('product_id', '=', self.productA.id), ('picking_id', '=', picking_out.id)], limit=1).quantity
        self.assertEqual(aval_a_qty, 4.0, 'Wrong move quantity availability of product A (%s found instead of 4)' % (aval_a_qty))
        # Check availability for product B
        aval_b_qty = self.MoveObj.search([('product_id', '=', self.productB.id), ('picking_id', '=', picking_out.id)], limit=1).quantity
        self.assertEqual(aval_b_qty, 5.0, 'Wrong move quantity availability of product B (%s found instead of 5)' % (aval_b_qty))
        # Check availability for product C
        aval_c_qty = self.MoveObj.search([('product_id', '=', self.productC.id), ('picking_id', '=', picking_out.id)], limit=1).quantity
        self.assertEqual(aval_c_qty, 3.0, 'Wrong move quantity availability of product C (%s found instead of 3)' % (aval_c_qty))
        # Check availability for product D
        aval_d_qty = self.MoveObj.search([('product_id', '=', self.productD.id), ('picking_id', '=', picking_out.id)], limit=1).quantity
        self.assertEqual(aval_d_qty, 7.0, 'Wrong move quantity availability of product D (%s found instead of 7)' % (aval_d_qty))

        # ----------------------------------------------------------------------
        # Replace pack operation of outgoing shipment.
        # ----------------------------------------------------------------------

        move_cust_a.move_line_ids.quantity = 2.0
        move_cust_b.move_line_ids.quantity = 3.0
        self.StockPackObj.create({
            'product_id': self.productB.id,
            'quantity': 2,
            'product_uom_id': self.productB.uom_id.id,
            'location_id': self.stock_location,
            'location_dest_id': self.customer_location,
            'move_id': move_cust_b.id})
        # TODO care if product_qty and lot_id are set at the same times the system do 2 unreserve.
        move_cust_c.move_line_ids[0].write({
            'quantity': 2.0,
            'lot_id': lot2_productC.id,
        })
        move_cust_c.move_line_ids[1].write({
            'quantity': 3.0,
        })
        move_cust_d.move_line_ids.quantity = 6.0

        # Transfer picking.
        (move_cust_a | move_cust_b | move_cust_c | move_cust_d).picked = True
        picking_out._action_done()

        # ----------------------------------------------------------------------
        # Check state, quantity and total moves of outgoing shipment.
        # ----------------------------------------------------------------------

        # check outgoing shipment status.
        self.assertEqual(picking_out.state, 'done', 'Wrong state of outgoing shipment.')
        # check outgoing shipment total moves and and its state.
        self.assertEqual(len(picking_out.move_ids), 4, 'Wrong number of move lines')
        for move in picking_out.move_ids:
            self.assertEqual(move.state, 'done', 'Wrong state of move line.')
        back_order_out = self.PickingObj.search([('backorder_id', '=', picking_out.id)])

        # ------------------
        # Check back order.
        # -----------------

        self.assertEqual(len(back_order_out), 1, 'Back order should be created.')
        # Check total move lines of back order.
        self.assertEqual(len(back_order_out.move_ids), 2, 'Wrong number of move lines')
        # Check back order should be created with 8 quantity of product A.
        product_a_qty = self.MoveObj.search([('product_id', '=', self.productA.id), ('picking_id', '=', back_order_out.id)], limit=1).product_uom_qty
        self.assertEqual(product_a_qty, 8.0, 'Wrong move quantity of product A (%s found instead of 8)' % (product_a_qty))
        # Check back order should be created with 4 quantity of product D.
        product_d_qty = self.MoveObj.search([('product_id', '=', self.productD.id), ('picking_id', '=', back_order_out.id)], limit=1).product_uom_qty
        self.assertEqual(product_d_qty, 4.0, 'Wrong move quantity of product D (%s found instead of 4)' % (product_d_qty))

        # -----------------------------------------------------------------------
        # Check stock location quant quantity and quantity available
        # of product A, B, C, D
        # -----------------------------------------------------------------------

        # Check quants and available quantity for product A
        quants = self.StockQuantObj.search([('product_id', '=', self.productA.id), ('location_id', '=', self.stock_location)])
        total_qty = [quant.quantity for quant in quants]

        self.assertEqual(sum(total_qty), 2.0, 'Expecting 2.0 Unit , got %.4f Unit on location stock!' % (sum(total_qty)))
        self.assertEqual(self.productA.qty_available, 2.0, 'Wrong quantity available (%s found instead of 2.0)' % (self.productA.qty_available))
        # Check quants and available quantity for product B
        quants = self.StockQuantObj.search([('product_id', '=', self.productB.id), ('location_id', '=', self.stock_location), ('quantity', '!=', 0)])
        self.assertFalse(quants, 'No quant should found as outgoing shipment took everything out of stock.')
        self.assertEqual(self.productB.qty_available, 0.0, 'Product B should have zero quantity available.')
        # Check quants and available quantity for product C
        quants = self.StockQuantObj.search([('product_id', '=', self.productC.id), ('location_id', '=', self.stock_location), ('quantity', '!=', 0)])
        total_qty = [quant.quantity for quant in quants]
        self.assertEqual(sum(total_qty), 2.0, 'Expecting 2.0 Unit, got %.4f Unit on location stock!' % (sum(total_qty)))
        self.assertEqual(self.productC.qty_available, 2.0, 'Wrong quantity available (%s found instead of 2.0)' % (self.productC.qty_available))
        # Check quants and available quantity for product D
        quant = self.StockQuantObj.search([('product_id', '=', self.productD.id), ('location_id', '=', self.stock_location), ('quantity', '!=', 0)], limit=1)
        self.assertEqual(quant.quantity, 1.0, 'Expecting 1.0 Unit , got %.4f Unit on location stock!' % (quant.quantity))
        self.assertEqual(self.productD.qty_available, 1.0, 'Wrong quantity available (%s found instead of 1.0)' % (self.productD.qty_available))

        # -----------------------------------------------------------------------
        # Back Order of Incoming shipment
        # -----------------------------------------------------------------------

        lot3_productC = LotObj.create({'name': 'Lot 3', 'product_id': self.productC.id, 'company_id': self.env.company.id})
        lot4_productC = LotObj.create({'name': 'Lot 4', 'product_id': self.productC.id, 'company_id': self.env.company.id})
        lot5_productC = LotObj.create({'name': 'Lot 5', 'product_id': self.productC.id, 'company_id': self.env.company.id})
        lot6_productC = LotObj.create({'name': 'Lot 6', 'product_id': self.productC.id, 'company_id': self.env.company.id})
        lot1_productD = LotObj.create({'name': 'Lot 1', 'product_id': self.productD.id, 'company_id': self.env.company.id})
        LotObj.create({'name': 'Lot 2', 'product_id': self.productD.id, 'company_id': self.env.company.id})

        # Confirm back order of incoming shipment.
        back_order_in.action_confirm()
        self.assertEqual(back_order_in.state, 'assigned', 'Wrong state of incoming shipment back order: %s instead of %s' % (back_order_in.state, 'assigned'))
        for move in back_order_in.move_ids:
            self.assertEqual(move.state, 'assigned', 'Wrong state of move line.')

        # ----------------------------------------------------------------------
        # Replace pack operation (Back order of Incoming shipment)
        # ----------------------------------------------------------------------

        packD = self.StockPackObj.search([('product_id', '=', self.productD.id), ('picking_id', '=', back_order_in.id)], order='quantity')
        self.assertEqual(len(packD), 1, 'Wrong number of pack operation.')
        packD[0].write({
            'quantity': 8,
            'lot_id': lot1_productD.id,
        })
        packCs = self.StockPackObj.search([('product_id', '=', self.productC.id), ('picking_id', '=', back_order_in.id)], limit=1)
        packCs.write({
            'quantity': 1,
            'lot_id': lot3_productC.id,
        })
        self.StockPackObj.create({
            'product_id': self.productC.id,
            'quantity': 1,
            'product_uom_id': self.productC.uom_id.id,
            'location_id': self.supplier_location,
            'location_dest_id': self.stock_location,
            'picking_id': back_order_in.id,
            'lot_id': lot4_productC.id,
        })
        self.StockPackObj.create({
            'product_id': self.productC.id,
            'quantity': 2,
            'product_uom_id': self.productC.uom_id.id,
            'location_id': self.supplier_location,
            'location_dest_id': self.stock_location,
            'picking_id': back_order_in.id,
            'lot_id': lot5_productC.id,
        })
        self.StockPackObj.create({
            'product_id': self.productC.id,
            'quantity': 2,
            'product_uom_id': self.productC.uom_id.id,
            'location_id': self.supplier_location,
            'location_dest_id': self.stock_location,
            'picking_id': back_order_in.id,
            'lot_id': lot6_productC.id,
        })
        self.StockPackObj.create({
            'product_id': self.productA.id,
            'quantity': 10,
            'product_uom_id': self.productA.uom_id.id,
            'location_id': self.supplier_location,
            'location_dest_id': self.stock_location,
            'picking_id': back_order_in.id
        })
        back_order_in.move_ids.picked = True
        back_order_in._action_done()

        # ----------------------------------------------------------------------
        # Check state, quantity and total moves (Back order of Incoming shipment).
        # ----------------------------------------------------------------------

        # Check total no of move lines.
        self.assertEqual(len(back_order_in.move_ids), 3, 'Wrong number of move lines')
        # Check incoming shipment state must be 'Done'.
        self.assertEqual(back_order_in.state, 'done', 'Wrong state of picking.')
        # Check incoming shipment move lines state must be 'Done'.
        for move in back_order_in.move_ids:
            self.assertEqual(move.state, 'done', 'Wrong state of move lines.')
        # Check product A done quantity must be 10
        movesA = self.MoveObj.search([('product_id', '=', self.productA.id), ('picking_id', '=', back_order_in.id)])
        self.assertEqual(movesA.quantity, 10, "Wrong move quantity of product A (%s found instead of 10)" % (movesA.quantity))
        # Check product C done quantity must be 3.0, 1.0, 2.0
        movesC = self.MoveObj.search([('product_id', '=', self.productC.id), ('picking_id', '=', back_order_in.id)])
        self.assertEqual(movesC.quantity, 6.0, 'Wrong quantity of moves product C.')
        # Check product D done quantity must be 5.0 and 3.0
        movesD = self.MoveObj.search([('product_id', '=', self.productD.id), ('picking_id', '=', back_order_in.id)])
        d_done_qty = [move.quantity for move in movesD]
        self.assertEqual(set(d_done_qty), set([8.0]), 'Wrong quantity of moves product D.')
        # Check no back order is created.
        self.assertFalse(self.PickingObj.search([('backorder_id', '=', back_order_in.id)]), "Should not create any back order.")

        # -----------------------------------------------------------------------
        # Check stock location quant quantity and quantity available
        # of product A, B, C, D
        # -----------------------------------------------------------------------

        # Check quants and available quantity for product A.
        quants = self.StockQuantObj.search([('product_id', '=', self.productA.id), ('location_id', '=', self.stock_location), ('quantity', '!=', 0)])
        total_qty = [quant.quantity for quant in quants]
        self.assertEqual(sum(total_qty), 12.0, 'Wrong total stock location quantity (%s found instead of 12)' % (sum(total_qty)))
        self.assertEqual(self.productA.qty_available, 12.0, 'Wrong quantity available (%s found instead of 12)' % (self.productA.qty_available))
        # Check quants and available quantity for product B.
        quants = self.StockQuantObj.search([('product_id', '=', self.productB.id), ('location_id', '=', self.stock_location), ('quantity', '!=', 0)])
        self.assertFalse(quants, 'No quant should found as outgoing shipment took everything out of stock')
        self.assertEqual(self.productB.qty_available, 0.0, 'Total quantity in stock should be 0 as the backorder took everything out of stock')
        # Check quants and available quantity for product C.
        quants = self.StockQuantObj.search([('product_id', '=', self.productC.id), ('location_id', '=', self.stock_location), ('quantity', '!=', 0)])
        total_qty = [quant.quantity for quant in quants]
        self.assertEqual(sum(total_qty), 8.0, 'Wrong total stock location quantity (%s found instead of 8)' % (sum(total_qty)))
        self.assertEqual(self.productC.qty_available, 8.0, 'Wrong quantity available (%s found instead of 8)' % (self.productC.qty_available))
        # Check quants and available quantity for product D.
        quants = self.StockQuantObj.search([('product_id', '=', self.productD.id), ('location_id', '=', self.stock_location), ('quantity', '!=', 0)])
        total_qty = [quant.quantity for quant in quants]
        self.assertEqual(sum(total_qty), 9.0, 'Wrong total stock location quantity (%s found instead of 9)' % (sum(total_qty)))
        self.assertEqual(self.productD.qty_available, 9.0, 'Wrong quantity available (%s found instead of 9)' % (self.productD.qty_available))

        # -----------------------------------------------------------------------
        # Back order of Outgoing shipment
        # ----------------------------------------------------------------------

        back_order_out._action_done()

        # Check stock location quants and available quantity for product A.
        quants = self.StockQuantObj.search([('product_id', '=', self.productA.id), ('location_id', '=', self.stock_location), ('quantity', '!=', 0)])
        total_qty = [quant.quantity for quant in quants]
        self.assertGreaterEqual(float_round(sum(total_qty), precision_rounding=0.0001), 1, 'Total stock location quantity for product A should not be nagative.')

    def test_10_pickings_transfer_with_different_uom(self):
        """ Picking transfer with diffrent unit of meassure. """

        # ----------------------------------------------------------------------
        # Create incoming shipment of products DozA, SDozA, SDozARound, kgB, gB
        # ----------------------------------------------------------------------
        #   DozA ( 10 Dozen ) , SDozA ( 10.5 SuperDozen )
        #   SDozARound ( 10.5 10.5 SuperDozenRound ) , kgB ( 0.020 kg )
        #   gB ( 525.3 g )
        # ----------------------------------------------------------------------

        picking_in_A = self.PickingObj.create({
            'picking_type_id': self.picking_type_in,
            'location_id': self.supplier_location,
            'state': 'draft',
            'location_dest_id': self.stock_location})
        self.MoveObj.create({
            'name': self.DozA.name,
            'product_id': self.DozA.id,
            'product_uom_qty': 10,
            'product_uom': self.DozA.uom_id.id,
            'picking_id': picking_in_A.id,
            'location_id': self.supplier_location,
            'location_dest_id': self.stock_location})
        self.MoveObj.create({
            'name': self.SDozA.name,
            'product_id': self.SDozA.id,
            'product_uom_qty': 10.5,
            'product_uom': self.SDozA.uom_id.id,
            'picking_id': picking_in_A.id,
            'location_id': self.supplier_location,
            'location_dest_id': self.stock_location})
        self.MoveObj.create({
            'name': self.SDozARound.name,
            'product_id': self.SDozARound.id,
            'product_uom_qty': 10.5,
            'product_uom': self.SDozARound.uom_id.id,
            'picking_id': picking_in_A.id,
            'location_id': self.supplier_location,
            'location_dest_id': self.stock_location})
        self.MoveObj.create({
            'name': self.kgB.name,
            'product_id': self.kgB.id,
            'product_uom_qty': 0.020,
            'product_uom': self.kgB.uom_id.id,
            'picking_id': picking_in_A.id,
            'location_id': self.supplier_location,
            'location_dest_id': self.stock_location})
        self.MoveObj.create({
            'name': self.gB.name,
            'product_id': self.gB.id,
            'product_uom_qty': 525.3,
            'product_uom': self.gB.uom_id.id,
            'picking_id': picking_in_A.id,
            'location_id': self.supplier_location,
            'location_dest_id': self.stock_location})

        # Check incoming shipment move lines state.
        for move in picking_in_A.move_ids:
            self.assertEqual(move.state, 'draft', 'Move state must be draft.')
        # Confirm incoming shipment.
        picking_in_A.action_confirm()
        # Check incoming shipment move lines state.
        for move in picking_in_A.move_ids:
            self.assertEqual(move.state, 'assigned', 'Move state must be draft.')

        # ----------------------------------------------------
        # Check pack operation quantity of incoming shipments.
        # ----------------------------------------------------

        PackSdozAround = self.StockPackObj.search([('product_id', '=', self.SDozARound.id), ('picking_id', '=', picking_in_A.id)], limit=1)
        self.assertEqual(PackSdozAround.quantity, 11, 'Wrong quantity in pack operation (%s found instead of 11)' % (PackSdozAround.quantity))
        picking_in_A.button_validate()

        # -----------------------------------------------------------------------
        # Check stock location quant quantity and quantity available
        # -----------------------------------------------------------------------

        # Check quants and available quantity for product DozA
        quants = self.StockQuantObj.search([('product_id', '=', self.DozA.id), ('location_id', '=', self.stock_location)])
        total_qty = [quant.quantity for quant in quants]
        self.assertEqual(sum(total_qty), 10, 'Expecting 10 Dozen , got %.4f Dozen on location stock!' % (sum(total_qty)))
        self.assertEqual(self.DozA.qty_available, 10, 'Wrong quantity available (%s found instead of 10)' % (self.DozA.qty_available))
        # Check quants and available quantity for product SDozA
        quants = self.StockQuantObj.search([('product_id', '=', self.SDozA.id), ('location_id', '=', self.stock_location)])
        total_qty = [quant.quantity for quant in quants]
        self.assertEqual(sum(total_qty), 10.5, 'Expecting 10.5 SDozen , got %.4f SDozen on location stock!' % (sum(total_qty)))
        self.assertEqual(self.SDozA.qty_available, 10.5, 'Wrong quantity available (%s found instead of 10.5)' % (self.SDozA.qty_available))
        # Check quants and available quantity for product SDozARound
        quants = self.StockQuantObj.search([('product_id', '=', self.SDozARound.id), ('location_id', '=', self.stock_location)])
        total_qty = [quant.quantity for quant in quants]
        self.assertEqual(sum(total_qty), 11, 'Expecting 11 SDozenRound , got %.4f SDozenRound on location stock!' % (sum(total_qty)))
        self.assertEqual(self.SDozARound.qty_available, 11, 'Wrong quantity available (%s found instead of 11)' % (self.SDozARound.qty_available))
        # Check quants and available quantity for product gB
        quants = self.StockQuantObj.search([('product_id', '=', self.gB.id), ('location_id', '=', self.stock_location)])
        total_qty = [quant.quantity for quant in quants]
        self.assertAlmostEqual(sum(total_qty), 525.3, msg='Expecting 525.3 gram , got %.4f gram on location stock!' % (sum(total_qty)))
        self.assertAlmostEqual(self.gB.qty_available, 525.3, msg='Wrong quantity available (%s found instead of 525.3' % (self.gB.qty_available))
        # Check quants and available quantity for product kgB
        quants = self.StockQuantObj.search([('product_id', '=', self.kgB.id), ('location_id', '=', self.stock_location)])
        total_qty = [quant.quantity for quant in quants]
        self.assertEqual(sum(total_qty), 0.020, 'Expecting 0.020 kg , got %.4f kg on location stock!' % (sum(total_qty)))
        self.assertEqual(self.kgB.qty_available, 0.020, 'Wrong quantity available (%s found instead of 0.020)' % (self.kgB.qty_available))

        # ----------------------------------------------------------------------
        # Create Incoming Shipment B
        # ----------------------------------------------------------------------

        picking_in_B = self.PickingObj.create({
            'picking_type_id': self.picking_type_in,
            'location_id': self.supplier_location,
            'state': 'draft',
            'location_dest_id': self.stock_location})
        move_in_a = self.MoveObj.create({
            'name': self.DozA.name,
            'product_id': self.DozA.id,
            'product_uom_qty': 120,
            'product_uom': self.uom_unit.id,
            'picking_id': picking_in_B.id,
            'location_id': self.supplier_location,
            'location_dest_id': self.stock_location})
        self.MoveObj.create({
            'name': self.SDozA.name,
            'product_id': self.SDozA.id,
            'product_uom_qty': 1512,
            'product_uom': self.uom_unit.id,
            'picking_id': picking_in_B.id,
            'location_id': self.supplier_location,
            'location_dest_id': self.stock_location})
        self.MoveObj.create({
            'name': self.SDozARound.name,
            'product_id': self.SDozARound.id,
            'product_uom_qty': 1584,
            'product_uom': self.uom_unit.id,
            'picking_id': picking_in_B.id,
            'location_id': self.supplier_location,
            'location_dest_id': self.stock_location})
        self.MoveObj.create({
            'name': self.kgB.name,
            'product_id': self.kgB.id,
            'product_uom_qty': 20.0,
            'product_uom': self.uom_gm.id,
            'picking_id': picking_in_B.id,
            'location_id': self.supplier_location,
            'location_dest_id': self.stock_location})
        self.MoveObj.create({
            'name': self.gB.name,
            'product_id': self.gB.id,
            'product_uom_qty': 0.525,
            'product_uom': self.uom_kg.id,
            'picking_id': picking_in_B.id,
            'location_id': self.supplier_location,
            'location_dest_id': self.stock_location})

        # Check incoming shipment move lines state.
        for move in picking_in_B.move_ids:
            self.assertEqual(move.state, 'draft', 'Wrong state of move line.')
        # Confirm incoming shipment.
        picking_in_B.action_confirm()
        # Check incoming shipment move lines state.
        for move in picking_in_B.move_ids:
            self.assertEqual(move.state, 'assigned', 'Wrong state of move line.')

        # ----------------------------------------------------------------------
        # Check product quantity and unit of measure of pack operaation.
        # ----------------------------------------------------------------------

        # Check pack operation quantity and unit of measure for product DozA.
        PackdozA = self.StockPackObj.search([('product_id', '=', self.DozA.id), ('picking_id', '=', picking_in_B.id)], limit=1)
        self.assertEqual(PackdozA.quantity, 120, 'Wrong quantity in pack operation (%s found instead of 120)' % (PackdozA.quantity))
        self.assertEqual(PackdozA.quantity_product_uom, 10, 'Wrong real quantity in pack operation (%s found instead of 10)' % (PackdozA.quantity_product_uom))
        self.assertEqual(PackdozA.product_uom_id.id, self.uom_unit.id, 'Wrong uom in pack operation for product DozA.')
        # Check pack operation quantity and unit of measure for product SDozA.
        PackSdozA = self.StockPackObj.search([('product_id', '=', self.SDozA.id), ('picking_id', '=', picking_in_B.id)], limit=1)
        self.assertEqual(PackSdozA.quantity, 1512, 'Wrong quantity in pack operation (%s found instead of 1512)' % (PackSdozA.quantity))
        self.assertEqual(PackSdozA.product_uom_id.id, self.uom_unit.id, 'Wrong uom in pack operation for product SDozA.')
        # Check pack operation quantity and unit of measure for product SDozARound.
        PackSdozAround = self.StockPackObj.search([('product_id', '=', self.SDozARound.id), ('picking_id', '=', picking_in_B.id)], limit=1)
        self.assertEqual(PackSdozAround.quantity, 1584, 'Wrong quantity in pack operation (%s found instead of 1584)' % (PackSdozAround.quantity))
        self.assertEqual(PackSdozAround.product_uom_id.id, self.uom_unit.id, 'Wrong uom in pack operation for product SDozARound.')
        # Check pack operation quantity and unit of measure for product gB.
        packgB = self.StockPackObj.search([('product_id', '=', self.gB.id), ('picking_id', '=', picking_in_B.id)], limit=1)
        self.assertEqual(packgB.quantity, 0.525, 'Wrong quantity in pack operation (%s found instead of 0.525)' % (packgB.quantity))
        self.assertEqual(packgB.quantity_product_uom, 525, 'Wrong real quantity in pack operation (%s found instead of 525)' % (packgB.quantity_product_uom))
        self.assertEqual(packgB.product_uom_id.id, packgB.move_id.product_uom.id, 'Wrong uom in pack operation for product kgB.')
        # Check pack operation quantity and unit of measure for product kgB.
        packkgB = self.StockPackObj.search([('product_id', '=', self.kgB.id), ('picking_id', '=', picking_in_B.id)], limit=1)
        self.assertEqual(packkgB.quantity, 20.0, 'Wrong quantity in pack operation (%s found instead of 20)' % (packkgB.quantity))
        self.assertEqual(packkgB.product_uom_id.id, self.uom_gm.id, 'Wrong uom in pack operation for product kgB')

        # ----------------------------------------------------------------------
        # Replace pack operation of incoming shipment.
        # ----------------------------------------------------------------------

        self.StockPackObj.search([('product_id', '=', self.kgB.id), ('picking_id', '=', picking_in_B.id)]).write({
            'quantity': 0.020, 'product_uom_id': self.uom_kg.id})
        self.StockPackObj.search([('product_id', '=', self.gB.id), ('picking_id', '=', picking_in_B.id)]).write({
            'quantity': 526, 'product_uom_id': self.uom_gm.id})
        self.StockPackObj.search([('product_id', '=', self.DozA.id), ('picking_id', '=', picking_in_B.id)]).write({
            'quantity': 4, 'product_uom_id': self.uom_dozen.id})
        self.StockPackObj.create({
            'product_id': self.DozA.id,
            'quantity': 48,
            'product_uom_id': self.uom_unit.id,
            'location_id': self.supplier_location,
            'location_dest_id': self.stock_location,
            'move_id': move_in_a.id
        })

        # -----------------
        # Transfer product.
        # -----------------

        res_dict_for_back_order = picking_in_B.button_validate()
        backorder_wizard = self.env[(res_dict_for_back_order.get('res_model'))].browse(res_dict_for_back_order.get('res_id')).with_context(res_dict_for_back_order['context'])
        backorder_wizard.process()

        # -----------------------------------------------------------------------
        # Check incoming shipment
        # -----------------------------------------------------------------------
        # Check incoming shipment state.
        self.assertEqual(picking_in_B.state, 'done', 'Incoming shipment state should be done.')
        # Check incoming shipment move lines state.
        for move in picking_in_B.move_ids:
            self.assertEqual(move.state, 'done', 'Wrong state of move line.')
        # Check total done move lines for incoming shipment.
        self.assertEqual(len(picking_in_B.move_ids), 5, 'Wrong number of move lines')
        # Check product DozA done quantity.
        moves_DozA = self.MoveObj.search([('product_id', '=', self.DozA.id), ('picking_id', '=', picking_in_B.id)], limit=1)
        self.assertEqual(moves_DozA.quantity, 96, 'Wrong move quantity (%s found instead of 96)' % (moves_DozA.product_uom_qty))
        self.assertEqual(moves_DozA.product_uom.id, self.uom_unit.id, 'Wrong uom in move for product DozA.')
        # Check product SDozA done quantity.
        moves_SDozA = self.MoveObj.search([('product_id', '=', self.SDozA.id), ('picking_id', '=', picking_in_B.id)], limit=1)
        self.assertEqual(moves_SDozA.quantity, 1512, 'Wrong move quantity (%s found instead of 1512)' % (moves_SDozA.product_uom_qty))
        self.assertEqual(moves_SDozA.product_uom.id, self.uom_unit.id, 'Wrong uom in move for product SDozA.')
        # Check product SDozARound done quantity.
        moves_SDozARound = self.MoveObj.search([('product_id', '=', self.SDozARound.id), ('picking_id', '=', picking_in_B.id)], limit=1)
        self.assertEqual(moves_SDozARound.quantity, 1584, 'Wrong move quantity (%s found instead of 1584)' % (moves_SDozARound.product_uom_qty))
        self.assertEqual(moves_SDozARound.product_uom.id, self.uom_unit.id, 'Wrong uom in move for product SDozARound.')
        # Check product kgB done quantity.
        moves_kgB = self.MoveObj.search([('product_id', '=', self.kgB.id), ('picking_id', '=', picking_in_B.id)], limit=1)
        self.assertEqual(moves_kgB.quantity, 20, 'Wrong quantity in move (%s found instead of 20)' % (moves_kgB.product_uom_qty))
        self.assertEqual(moves_kgB.product_uom.id, self.uom_gm.id, 'Wrong uom in move for product kgB.')
        # Check two moves created for product gB with quantity (0.525 kg and 0.3 g)
        moves_gB_kg = self.MoveObj.search([('product_id', '=', self.gB.id), ('picking_id', '=', picking_in_B.id), ('product_uom', '=', self.uom_kg.id)], limit=1)
        self.assertEqual(moves_gB_kg.quantity, 0.526, 'Wrong move quantity (%s found instead of 0.526)' % (moves_gB_kg.product_uom_qty))
        self.assertEqual(moves_gB_kg.product_uom.id, self.uom_kg.id, 'Wrong uom in move for product gB.')

        # TODO Test extra move once the uom is editable in the move_lines

        # ----------------------------------------------------------------------
        # Check Back order of Incoming shipment.
        # ----------------------------------------------------------------------

        # Check back order created or not.
        bo_in_B = self.PickingObj.search([('backorder_id', '=', picking_in_B.id)])
        self.assertEqual(len(bo_in_B), 1, 'Back order should be created.')
        # Check total move lines of back order.
        self.assertEqual(len(bo_in_B.move_ids), 1, 'Wrong number of move lines')
        # Check back order created with correct quantity and uom or not.
        moves_DozA = self.MoveObj.search([('product_id', '=', self.DozA.id), ('picking_id', '=', bo_in_B.id)], limit=1)
        self.assertEqual(moves_DozA.product_uom_qty, 24.0, 'Wrong move quantity (%s found instead of 0.525)' % (moves_DozA.product_uom_qty))
        self.assertEqual(moves_DozA.product_uom.id, self.uom_unit.id, 'Wrong uom in move for product DozA.')

        # ----------------------------------------------------------------------
        # Check product stock location quantity and quantity available.
        # ----------------------------------------------------------------------

        # Check quants and available quantity for product DozA
        quants = self.StockQuantObj.search([('product_id', '=', self.DozA.id), ('location_id', '=', self.stock_location)])
        total_qty = [quant.quantity for quant in quants]
        self.assertEqual(sum(total_qty), 18, 'Expecting 18 Dozen , got %.4f Dozen on location stock!' % (sum(total_qty)))
        self.assertEqual(self.DozA.qty_available, 18, 'Wrong quantity available (%s found instead of 18)' % (self.DozA.qty_available))
        # Check quants and available quantity for product SDozA
        quants = self.StockQuantObj.search([('product_id', '=', self.SDozA.id), ('location_id', '=', self.stock_location)])
        total_qty = [quant.quantity for quant in quants]
        self.assertEqual(sum(total_qty), 21, 'Expecting 21 SDozen , got %.4f SDozen on location stock!' % (sum(total_qty)))
        self.assertEqual(self.SDozA.qty_available, 21, 'Wrong quantity available (%s found instead of 21)' % (self.SDozA.qty_available))
        # Check quants and available quantity for product SDozARound
        quants = self.StockQuantObj.search([('product_id', '=', self.SDozARound.id), ('location_id', '=', self.stock_location)])
        total_qty = [quant.quantity for quant in quants]
        self.assertEqual(sum(total_qty), 22, 'Expecting 22 SDozenRound , got %.4f SDozenRound on location stock!' % (sum(total_qty)))
        self.assertEqual(self.SDozARound.qty_available, 22, 'Wrong quantity available (%s found instead of 22)' % (self.SDozARound.qty_available))
        # Check quants and available quantity for product gB.
        quants = self.StockQuantObj.search([('product_id', '=', self.gB.id), ('location_id', '=', self.stock_location)])
        total_qty = [quant.quantity for quant in quants]
        self.assertEqual(round(sum(total_qty), 1), 1051.3, 'Expecting 1051 Gram , got %.4f Gram on location stock!' % (sum(total_qty)))
        self.assertEqual(round(self.gB.qty_available, 1), 1051.3, 'Wrong quantity available (%s found instead of 1051)' % (self.gB.qty_available))
        # Check quants and available quantity for product kgB.
        quants = self.StockQuantObj.search([('product_id', '=', self.kgB.id), ('location_id', '=', self.stock_location)])
        total_qty = [quant.quantity for quant in quants]
        self.assertEqual(sum(total_qty), 0.040, 'Expecting 0.040 kg , got %.4f kg on location stock!' % (sum(total_qty)))
        self.assertEqual(self.kgB.qty_available, 0.040, 'Wrong quantity available (%s found instead of 0.040)' % (self.kgB.qty_available))

        # ----------------------------------------------------------------------
        # Create outgoing shipment.
        # ----------------------------------------------------------------------

        before_out_quantity = self.kgB.qty_available
        picking_out = self.PickingObj.create({
            'picking_type_id': self.picking_type_out,
            'location_id': self.stock_location,
            'state': 'draft',
            'location_dest_id': self.customer_location})
        self.MoveObj.create({
            'name': self.kgB.name,
            'product_id': self.kgB.id,
            'product_uom_qty': 0.966,
            'product_uom': self.uom_gm.id,
            'picking_id': picking_out.id,
            'location_id': self.stock_location,
            'location_dest_id': self.customer_location})
        self.MoveObj.create({
            'name': self.kgB.name,
            'product_id': self.kgB.id,
            'product_uom_qty': 0.034,
            'product_uom': self.uom_gm.id,
            'picking_id': picking_out.id,
            'location_id': self.stock_location,
            'location_dest_id': self.customer_location})
        picking_out.action_confirm()
        picking_out.action_assign()
        picking_out.button_validate()

        # Check quantity difference after stock transfer.
        quantity_diff = before_out_quantity - self.kgB.qty_available
        self.assertEqual(float_round(quantity_diff, precision_rounding=0.0001), 0.001, 'Wrong quantity difference.')
        self.assertEqual(self.kgB.qty_available, 0.039, 'Wrong quantity available (%s found instead of 0.039)' % (self.kgB.qty_available))

        # ======================================================================
        # Outgoing shipments.
        # ======================================================================

        # Create Outgoing shipment with ...
        #   product DozA ( 54 Unit ) , SDozA ( 288 Unit )
        #   product SDozRound (  360 unit ) , product gB ( 0.503 kg )
        #   product kgB (  19 g )
        # ======================================================================

        picking_out = self.PickingObj.create({
            'picking_type_id': self.picking_type_out,
            'location_id': self.stock_location,
            'state': 'draft',
            'location_dest_id': self.customer_location})
        self.MoveObj.create({
            'name': self.DozA.name,
            'product_id': self.DozA.id,
            'product_uom_qty': 54,
            'product_uom': self.uom_unit.id,
            'picking_id': picking_out.id,
            'location_id': self.stock_location,
            'location_dest_id': self.customer_location})
        self.MoveObj.create({
            'name': self.SDozA.name,
            'product_id': self.SDozA.id,
            'product_uom_qty': 288,
            'product_uom': self.uom_unit.id,
            'picking_id': picking_out.id,
            'location_id': self.stock_location,
            'location_dest_id': self.customer_location})
        self.MoveObj.create({
            'name': self.SDozARound.name,
            'product_id': self.SDozARound.id,
            'product_uom_qty': 361,
            'product_uom': self.uom_unit.id,
            'picking_id': picking_out.id,
            'location_id': self.stock_location,
            'location_dest_id': self.customer_location})
        self.MoveObj.create({
            'name': self.gB.name,
            'product_id': self.gB.id,
            'product_uom_qty': 0.503,
            'product_uom': self.uom_kg.id,
            'picking_id': picking_out.id,
            'location_id': self.stock_location,
            'location_dest_id': self.customer_location})
        self.MoveObj.create({
            'name': self.kgB.name,
            'product_id': self.kgB.id,
            'product_uom_qty': 20,
            'product_uom': self.uom_gm.id,
            'picking_id': picking_out.id,
            'location_id': self.stock_location,
            'location_dest_id': self.customer_location})
        # Confirm outgoing shipment.
        picking_out.action_confirm()
        for move in picking_out.move_ids:
            self.assertEqual(move.state, 'confirmed', 'Wrong state of move line.')
        # Assing product to outgoing shipments
        picking_out.action_assign()
        for move in picking_out.move_ids:
            self.assertEqual(move.state, 'assigned', 'Wrong state of move line.')
        # Check product A available quantity
        DozA_qty = self.MoveObj.search([('product_id', '=', self.DozA.id), ('picking_id', '=', picking_out.id)], limit=1).product_qty
        self.assertEqual(DozA_qty, 4.5, 'Wrong move quantity availability (%s found instead of 4.5)' % (DozA_qty))
        # Check product B available quantity
        SDozA_qty = self.MoveObj.search([('product_id', '=', self.SDozA.id), ('picking_id', '=', picking_out.id)], limit=1).product_qty
        self.assertEqual(SDozA_qty, 2, 'Wrong move quantity availability (%s found instead of 2)' % (SDozA_qty))
        # Check product C available quantity
        SDozARound_qty = self.MoveObj.search([('product_id', '=', self.SDozARound.id), ('picking_id', '=', picking_out.id)], limit=1).product_qty
        self.assertEqual(SDozARound_qty, 3, 'Wrong move quantity availability (%s found instead of 3)' % (SDozARound_qty))
        # Check product D available quantity
        gB_qty = self.MoveObj.search([('product_id', '=', self.gB.id), ('picking_id', '=', picking_out.id)], limit=1).product_qty
        self.assertEqual(gB_qty, 503, 'Wrong move quantity availability (%s found instead of 503)' % (gB_qty))
        # Check product D available quantity
        kgB_qty = self.MoveObj.search([('product_id', '=', self.kgB.id), ('picking_id', '=', picking_out.id)], limit=1).product_qty
        self.assertEqual(kgB_qty, 0.020, 'Wrong move quantity availability (%s found instead of 0.020)' % (kgB_qty))

        picking_out.button_validate()
        # ----------------------------------------------------------------------
        # Check product stock location quantity and quantity available.
        # ----------------------------------------------------------------------

        # Check quants and available quantity for product DozA
        quants = self.StockQuantObj.search([('product_id', '=', self.DozA.id), ('location_id', '=', self.stock_location)])
        total_qty = [quant.quantity for quant in quants]
        self.assertEqual(sum(total_qty), 13.5, 'Expecting 13.5 Dozen , got %.4f Dozen on location stock!' % (sum(total_qty)))
        self.assertEqual(self.DozA.qty_available, 13.5, 'Wrong quantity available (%s found instead of 13.5)' % (self.DozA.qty_available))
        # Check quants and available quantity for product SDozA
        quants = self.StockQuantObj.search([('product_id', '=', self.SDozA.id), ('location_id', '=', self.stock_location)])
        total_qty = [quant.quantity for quant in quants]
        self.assertEqual(sum(total_qty), 19, 'Expecting 19 SDozen , got %.4f SDozen on location stock!' % (sum(total_qty)))
        self.assertEqual(self.SDozA.qty_available, 19, 'Wrong quantity available (%s found instead of 19)' % (self.SDozA.qty_available))
        # Check quants and available quantity for product SDozARound
        quants = self.StockQuantObj.search([('product_id', '=', self.SDozARound.id), ('location_id', '=', self.stock_location)])
        total_qty = [quant.quantity for quant in quants]
        self.assertEqual(sum(total_qty), 19, 'Expecting 19 SDozRound , got %.4f SDozRound on location stock!' % (sum(total_qty)))
        self.assertEqual(self.SDozARound.qty_available, 19, 'Wrong quantity available (%s found instead of 19)' % (self.SDozARound.qty_available))
        # Check quants and available quantity for product gB.
        quants = self.StockQuantObj.search([('product_id', '=', self.gB.id), ('location_id', '=', self.stock_location)])
        total_qty = [quant.quantity for quant in quants]
        self.assertEqual(round(sum(total_qty), 1), 548.3, 'Expecting 547.6 g , got %.4f g on location stock!' % (sum(total_qty)))
        self.assertEqual(round(self.gB.qty_available, 1), 548.3, 'Wrong quantity available (%s found instead of 547.6)' % (self.gB.qty_available))
        # Check quants and available quantity for product kgB.
        quants = self.StockQuantObj.search([('product_id', '=', self.kgB.id), ('location_id', '=', self.stock_location)])
        total_qty = [quant.quantity for quant in quants]
        self.assertEqual(sum(total_qty), 0.019, 'Expecting 0.019 kg , got %.4f kg on location stock!' % (sum(total_qty)))
        self.assertEqual(self.kgB.qty_available, 0.019, 'Wrong quantity available (%s found instead of 0.019)' % (self.kgB.qty_available))

        # ----------------------------------------------------------------------
        # Receipt back order of incoming shipment.
        # ----------------------------------------------------------------------

        bo_in_B.button_validate()
        # Check quants and available quantity for product kgB.
        quants = self.StockQuantObj.search([('product_id', '=', self.DozA.id), ('location_id', '=', self.stock_location)])
        total_qty = [quant.quantity for quant in quants]
        self.assertEqual(sum(total_qty), 15.5, 'Expecting 15.5 Dozen , got %.4f Dozen on location stock!' % (sum(total_qty)))
        self.assertEqual(self.DozA.qty_available, 15.5, 'Wrong quantity available (%s found instead of 15.5)' % (self.DozA.qty_available))

        # -----------------------------------------
        # Create product in kg and receive in ton.
        # -----------------------------------------

        productKG = self.ProductObj.create({'name': 'Product KG', 'uom_id': self.uom_kg.id, 'uom_po_id': self.uom_kg.id, 'type': 'product'})
        picking_in = self.PickingObj.create({
            'picking_type_id': self.picking_type_in,
            'location_id': self.supplier_location,
            'state': 'draft',
            'location_dest_id': self.stock_location})
        self.MoveObj.create({
            'name': productKG.name,
            'product_id': productKG.id,
            'product_uom_qty': 1.0,
            'product_uom': self.uom_tone.id,
            'picking_id': picking_in.id,
            'location_id': self.supplier_location,
            'location_dest_id': self.stock_location})
        # Check incoming shipment state.
        self.assertEqual(picking_in.state, 'draft', 'Incoming shipment state should be draft.')
        # Check incoming shipment move lines state.
        for move in picking_in.move_ids:
            self.assertEqual(move.state, 'draft', 'Wrong state of move line.')
        # Confirm incoming shipment.
        picking_in.action_confirm()
        # Check incoming shipment move lines state.
        for move in picking_in.move_ids:
            self.assertEqual(move.state, 'assigned', 'Wrong state of move line.')
        # Check pack operation quantity.
        packKG = self.StockPackObj.search([('product_id', '=', productKG.id), ('picking_id', '=', picking_in.id)], limit=1)
        self.assertEqual(packKG.quantity_product_uom, 1000, 'Wrong product real quantity in pack operation (%s found instead of 1000)' % (packKG.quantity_product_uom))
        self.assertEqual(packKG.quantity, 1, 'Wrong product quantity in pack operation (%s found instead of 1)' % (packKG.quantity))
        self.assertEqual(packKG.product_uom_id.id, self.uom_tone.id, 'Wrong product uom in pack operation.')
        # Transfer Incoming shipment.
        picking_in.button_validate()

        # -----------------------------------------------------------------------
        # Check incoming shipment after transfer.
        # -----------------------------------------------------------------------

        # Check incoming shipment state.
        self.assertEqual(picking_in.state, 'done', 'Incoming shipment state: %s instead of %s' % (picking_in.state, 'done'))
        # Check incoming shipment move lines state.
        for move in picking_in.move_ids:
            self.assertEqual(move.state, 'done', 'Wrong state of move lines.')
        # Check total done move lines for incoming shipment.
        self.assertEqual(len(picking_in.move_ids), 1, 'Wrong number of move lines')
        # Check product DozA done quantity.
        move = self.MoveObj.search([('product_id', '=', productKG.id), ('picking_id', '=', picking_in.id)], limit=1)
        self.assertEqual(move.product_uom_qty, 1, 'Wrong product quantity in done move.')
        self.assertEqual(move.product_uom.id, self.uom_tone.id, 'Wrong unit of measure in done move.')
        self.assertEqual(productKG.qty_available, 1000, 'Wrong quantity available of product (%s found instead of 1000)' % (productKG.qty_available))
        picking_out = self.PickingObj.create({
            'picking_type_id': self.picking_type_out,
            'location_id': self.stock_location,
            'state': 'draft',
            'location_dest_id': self.customer_location})
        self.MoveObj.create({
            'name': productKG.name,
            'product_id': productKG.id,
            'product_uom_qty': 25,
            'product_uom': self.uom_gm.id,
            'picking_id': picking_out.id,
            'location_id': self.stock_location,
            'location_dest_id': self.customer_location})
        picking_out.action_confirm()
        picking_out.action_assign()
        pack_opt = self.StockPackObj.search([('product_id', '=', productKG.id), ('picking_id', '=', picking_out.id)], limit=1)
        pack_opt.write({'quantity': 5})
        res_dict_for_back_order = picking_out.button_validate()
        backorder_wizard = self.env[(res_dict_for_back_order.get('res_model'))].browse(res_dict_for_back_order.get('res_id')).with_context(res_dict_for_back_order['context'])
        backorder_wizard.process()
        quants = self.StockQuantObj.search([('product_id', '=', productKG.id), ('location_id', '=', self.stock_location)])
        total_qty = [quant.quantity for quant in quants]
        # Check total quantity stock location.
        self.assertEqual(sum(total_qty), 999.995, 'Expecting 999.995 kg , got %.4f kg on location stock!' % (sum(total_qty)))

        # ---------------------------------
        # Check Back order created or not.
        # ---------------------------------
        bo_out_1 = self.PickingObj.search([('backorder_id', '=', picking_out.id)])
        self.assertEqual(len(bo_out_1), 1, 'Back order should be created.')
        # Check total move lines of back order.
        self.assertEqual(len(bo_out_1.move_ids), 1, 'Wrong number of move lines')
        moves_KG = self.MoveObj.search([('product_id', '=', productKG.id), ('picking_id', '=', bo_out_1.id)], limit=1)
        # Check back order created with correct quantity and uom or not.
        self.assertEqual(moves_KG.product_uom_qty, 20, 'Wrong move quantity (%s found instead of 20)' % (moves_KG.product_uom_qty))
        self.assertEqual(moves_KG.product_uom.id, self.uom_gm.id, 'Wrong uom in move for product KG.')
        bo_out_1.action_assign()
        pack_opt = self.StockPackObj.search([('product_id', '=', productKG.id), ('picking_id', '=', bo_out_1.id)], limit=1)
        pack_opt.write({'quantity': 5})
        res_dict_for_back_order = bo_out_1.button_validate()
        backorder_wizard = self.env[(res_dict_for_back_order.get('res_model'))].browse(res_dict_for_back_order.get('res_id')).with_context(res_dict_for_back_order['context'])
        backorder_wizard.process()
        quants = self.StockQuantObj.search([('product_id', '=', productKG.id), ('location_id', '=', self.stock_location)])
        total_qty = [quant.quantity for quant in quants]

        # Check total quantity stock location.
        self.assertEqual(sum(total_qty), 999.990, 'Expecting 999.990 kg , got %.4f kg on location stock!' % (sum(total_qty)))

        # Check Back order created or not.
        # ---------------------------------
        bo_out_2 = self.PickingObj.search([('backorder_id', '=', bo_out_1.id)])
        self.assertEqual(len(bo_out_2), 1, 'Back order should be created.')
        # Check total move lines of back order.
        self.assertEqual(len(bo_out_2.move_ids), 1, 'Wrong number of move lines')
        # Check back order created with correct move quantity and uom or not.
        moves_KG = self.MoveObj.search([('product_id', '=', productKG.id), ('picking_id', '=', bo_out_2.id)], limit=1)
        self.assertEqual(moves_KG.product_uom_qty, 15, 'Wrong move quantity (%s found instead of 15)' % (moves_KG.product_uom_qty))
        self.assertEqual(moves_KG.product_uom.id, self.uom_gm.id, 'Wrong uom in move for product KG.')
        bo_out_2.action_assign()
        pack_opt = self.StockPackObj.search([('product_id', '=', productKG.id), ('picking_id', '=', bo_out_2.id)], limit=1)
        pack_opt.write({'quantity': 5})
        res_dict_for_back_order = bo_out_2.button_validate()
        backorder_wizard = self.env[(res_dict_for_back_order.get('res_model'))].browse(res_dict_for_back_order.get('res_id')).with_context(res_dict_for_back_order['context'])
        backorder_wizard.process()
        # Check total quantity stock location of product KG.
        quants = self.StockQuantObj.search([('product_id', '=', productKG.id), ('location_id', '=', self.stock_location)])
        total_qty = [quant.quantity for quant in quants]
        self.assertEqual(sum(total_qty), 999.985, 'Expecting 999.985 kg , got %.4f kg on location stock!' % (sum(total_qty)))

        # Check Back order created or not.
        # ---------------------------------
        bo_out_3 = self.PickingObj.search([('backorder_id', '=', bo_out_2.id)])
        self.assertEqual(len(bo_out_3), 1, 'Back order should be created.')
        # Check total move lines of back order.
        self.assertEqual(len(bo_out_3.move_ids), 1, 'Wrong number of move lines')
        # Check back order created with correct quantity and uom or not.
        moves_KG = self.MoveObj.search([('product_id', '=', productKG.id), ('picking_id', '=', bo_out_3.id)], limit=1)
        self.assertEqual(moves_KG.product_uom_qty, 10, 'Wrong move quantity (%s found instead of 10)' % (moves_KG.product_uom_qty))
        self.assertEqual(moves_KG.product_uom.id, self.uom_gm.id, 'Wrong uom in move for product KG.')
        bo_out_3.action_assign()
        pack_opt = self.StockPackObj.search([('product_id', '=', productKG.id), ('picking_id', '=', bo_out_3.id)], limit=1)
        pack_opt.write({'quantity': 5})
        res_dict_for_back_order = bo_out_3.button_validate()
        backorder_wizard = self.env[(res_dict_for_back_order.get('res_model'))].browse(res_dict_for_back_order.get('res_id')).with_context(res_dict_for_back_order['context'])
        backorder_wizard.process()
        quants = self.StockQuantObj.search([('product_id', '=', productKG.id), ('location_id', '=', self.stock_location)])
        total_qty = [quant.quantity for quant in quants]
        self.assertEqual(sum(total_qty), 999.980, 'Expecting 999.980 kg , got %.4f kg on location stock!' % (sum(total_qty)))

        # Check Back order created or not.
        # ---------------------------------
        bo_out_4 = self.PickingObj.search([('backorder_id', '=', bo_out_3.id)])

        self.assertEqual(len(bo_out_4), 1, 'Back order should be created.')
        # Check total move lines of back order.
        self.assertEqual(len(bo_out_4.move_ids), 1, 'Wrong number of move lines')
        # Check back order created with correct quantity and uom or not.
        moves_KG = self.MoveObj.search([('product_id', '=', productKG.id), ('picking_id', '=', bo_out_4.id)], limit=1)
        self.assertEqual(moves_KG.product_uom_qty, 5, 'Wrong move quantity (%s found instead of 5)' % (moves_KG.product_uom_qty))
        self.assertEqual(moves_KG.product_uom.id, self.uom_gm.id, 'Wrong uom in move for product KG.')
        bo_out_4.action_assign()
        pack_opt = self.StockPackObj.search([('product_id', '=', productKG.id), ('picking_id', '=', bo_out_4.id)], limit=1)
        pack_opt.write({'quantity': 5})
        bo_out_4.button_validate()
        quants = self.StockQuantObj.search([('product_id', '=', productKG.id), ('location_id', '=', self.stock_location)])
        total_qty = [quant.quantity for quant in quants]
        self.assertAlmostEqual(sum(total_qty), 999.975, msg='Expecting 999.975 kg , got %.4f kg on location stock!' % (sum(total_qty)))

    def test_20_create_inventory_with_packs_and_lots(self):
        # --------------------------------------------------------
        # TEST EMPTY INVENTORY WITH PACKS and LOTS
        # ---------------------------------------------------------

        packproduct = self.ProductObj.create({'name': 'Pack Product', 'uom_id': self.uom_unit.id, 'uom_po_id': self.uom_unit.id, 'type': 'product'})
        lotproduct = self.ProductObj.create({'name': 'Lot Product', 'uom_id': self.uom_unit.id, 'uom_po_id': self.uom_unit.id, 'type': 'product'})
        quant_obj = self.env['stock.quant'].with_context(inventory_mode=True)
        pack_obj = self.env['stock.quant.package']
        lot_obj = self.env['stock.lot']
        pack1 = pack_obj.create({'name': 'PACK00TEST1'})
        pack_obj.create({'name': 'PACK00TEST2'})
        lot1 = lot_obj.create({'name': 'Lot001', 'product_id': lotproduct.id, 'company_id': self.env.company.id})

        packproduct_no_pack_quant = quant_obj.create({
            'product_id': packproduct.id,
            'inventory_quantity': 10.0,
            'location_id': self.stock_location
        })
        packproduct_quant = quant_obj.create({
            'product_id': packproduct.id,
            'inventory_quantity': 20.0,
            'location_id': self.stock_location,
            'package_id': pack1.id
        })
        lotproduct_no_lot_quant = quant_obj.create({
            'product_id': lotproduct.id,
            'inventory_quantity': 25.0,
            'location_id': self.stock_location
        })
        lotproduct_quant = quant_obj.create({
            'product_id': lotproduct.id,
            'inventory_quantity': 30.0,
            'location_id': self.stock_location,
            'lot_id': lot1.id
        })
        (packproduct_no_pack_quant | packproduct_quant | lotproduct_no_lot_quant | lotproduct_quant).action_apply_inventory()

        self.assertEqual(packproduct.qty_available, 30, "Wrong qty available for packproduct")
        self.assertEqual(lotproduct.qty_available, 55, "Wrong qty available for lotproduct")
        quants = self.StockQuantObj.search([('product_id', '=', packproduct.id), ('location_id', '=', self.stock_location), ('package_id', '=', pack1.id)])
        total_qty = sum([quant.quantity for quant in quants])
        self.assertEqual(total_qty, 20, 'Expecting 20 units on package 1 of packproduct, but we got %.4f on location stock!' % (total_qty))

        # Create an inventory that will put the lots without lot to 0 and check that taking without pack will not take it from the pack
        packproduct_no_pack_quant.inventory_quantity = 20
        lotproduct_no_lot_quant.inventory_quantity = 0
        lotproduct_quant.inventory_quantity = 10
        packproduct_no_pack_quant.action_apply_inventory()
        lotproduct_no_lot_quant.action_apply_inventory()
        lotproduct_quant.action_apply_inventory()

        self.assertEqual(packproduct.qty_available, 40, "Wrong qty available for packproduct")
        self.assertEqual(lotproduct.qty_available, 10, "Wrong qty available for lotproduct")
        quants = self.StockQuantObj.search([('product_id', '=', lotproduct.id), ('location_id', '=', self.stock_location), ('lot_id', '=', lot1.id)])
        total_qty = sum([quant.quantity for quant in quants])
        self.assertEqual(total_qty, 10, 'Expecting 10 units lot of lotproduct, but we got %.4f on location stock!' % (total_qty))
        quants = self.StockQuantObj.search([('product_id', '=', lotproduct.id), ('location_id', '=', self.stock_location), ('lot_id', '=', False)])
        total_qty = sum([quant.quantity for quant in quants])
        self.assertEqual(total_qty, 0, 'Expecting 0 units lot of lotproduct, but we got %.4f on location stock!' % (total_qty))

    def test_30_check_with_no_incoming_lot(self):
        """ Picking in without lots and picking out with"""
        # Change basic operation type not to get lots
        # Create product with lot tracking
        picking_in = self.env['stock.picking.type'].browse(self.picking_type_in)
        picking_in.use_create_lots = False
        self.productA.tracking = 'lot'
        picking_in = self.PickingObj.create({
            'picking_type_id': self.picking_type_in,
            'location_id': self.supplier_location,
            'state': 'draft',
            'location_dest_id': self.stock_location})
        self.MoveObj.create({
            'name': self.productA.name,
            'product_id': self.productA.id,
            'product_uom_qty': 4,
            'product_uom': self.productA.uom_id.id,
            'picking_id': picking_in.id,
            'picking_type_id': self.picking_type_in,
            'location_id': self.supplier_location,
            'location_dest_id': self.stock_location})

        # Check incoming shipment move lines state.
        for move in picking_in.move_ids:
            self.assertEqual(move.state, 'draft', 'Wrong state of move line.')
        # Confirm incoming shipment.
        picking_in.action_confirm()
        # Check incoming shipment move lines state.
        for move in picking_in.move_ids:
            self.assertEqual(move.state, 'assigned', 'Wrong state of move line.')

        picking_in.button_validate()
        picking_out = self.PickingObj.create({
            'name': 'testpicking',
            'picking_type_id': self.picking_type_out,
            'location_id': self.stock_location,
            'state': 'draft',
            'location_dest_id': self.customer_location})
        move_out = self.MoveObj.create({
            'name': self.productA.name,
            'product_id': self.productA.id,
            'product_uom_qty': 3,
            'product_uom': self.productA.uom_id.id,
            'picking_id': picking_out.id,
            'location_id': self.stock_location,
            'location_dest_id': self.customer_location})
        picking_out.action_confirm()
        picking_out.action_assign()
        pack_opt = self.StockPackObj.search([('picking_id', '=', picking_out.id)], limit=1)
        lot1 = self.LotObj.create({'product_id': self.productA.id, 'name': 'LOT1', 'company_id': self.env.company.id})
        lot2 = self.LotObj.create({'product_id': self.productA.id, 'name': 'LOT2', 'company_id': self.env.company.id})
        lot3 = self.LotObj.create({'product_id': self.productA.id, 'name': 'LOT3', 'company_id': self.env.company.id})

        pack_opt.write({'lot_id': lot1.id, 'quantity': 1.0})
        self.StockPackObj.create({'product_id': self.productA.id, 'move_id': move_out.id, 'product_uom_id': move_out.product_uom.id, 'lot_id': lot2.id, 'quantity': 1.0, 'location_id': self.stock_location, 'location_dest_id': self.customer_location})
        self.StockPackObj.create({'product_id': self.productA.id, 'move_id': move_out.id, 'product_uom_id': move_out.product_uom.id, 'lot_id': lot3.id, 'quantity': 2.0, 'location_id': self.stock_location, 'location_dest_id': self.customer_location})
        picking_out._action_done()
        quants = self.StockQuantObj.search([('product_id', '=', self.productA.id), ('location_id', '=', self.stock_location)])

    def test_40_pack_in_pack(self):
        """ Put a pack in pack"""
        self.env['stock.picking.type'].browse(self.picking_type_in).show_reserved = True
        picking_out = self.PickingObj.create({
            'picking_type_id': self.picking_type_out,
            'location_id': self.pack_location,
            'state': 'draft',
            'location_dest_id': self.customer_location})
        move_out = self.MoveObj.create({
            'name': self.productA.name,
            'product_id': self.productA.id,
            'product_uom_qty': 3,
            'product_uom': self.productA.uom_id.id,
            'picking_id': picking_out.id,
            'location_id': self.pack_location,
            'location_dest_id': self.customer_location})
        picking_pack = self.PickingObj.create({
            'picking_type_id': self.picking_type_out,
            'location_id': self.stock_location,
            'state': 'draft',
            'location_dest_id': self.pack_location})
        move_pack = self.MoveObj.create({
            'name': self.productA.name,
            'product_id': self.productA.id,
            'product_uom_qty': 3,
            'product_uom': self.productA.uom_id.id,
            'picking_id': picking_pack.id,
            'location_id': self.stock_location,
            'location_dest_id': self.pack_location,
            'move_dest_ids': [(4, move_out.id, 0)]})
        picking_in = self.PickingObj.create({
            'picking_type_id': self.picking_type_in,
            'location_id': self.supplier_location,
            'state': 'draft',
            'location_dest_id': self.stock_location})
        move_in = self.MoveObj.create({
            'name': self.productA.name,
            'product_id': self.productA.id,
            'product_uom_qty': 3,
            'product_uom': self.productA.uom_id.id,
            'picking_id': picking_in.id,
            'location_id': self.supplier_location,
            'location_dest_id': self.stock_location,
            'move_dest_ids': [(4, move_pack.id, 0)]})

        # Check incoming shipment move lines state.
        for move in picking_in.move_ids:
            self.assertEqual(move.state, 'draft', 'Wrong state of move line.')
        # Confirm incoming shipment.
        picking_in.action_confirm()
        # Check incoming shipment move lines state.
        for move in picking_in.move_ids:
            self.assertEqual(move.state, 'assigned', 'Wrong state of move line.')

        # Check incoming shipment move lines state.
        for move in picking_pack.move_ids:
            self.assertEqual(move.state, 'draft', 'Wrong state of move line.')
        # Confirm incoming shipment.
        picking_pack.action_confirm()
        # Check incoming shipment move lines state.
        for move in picking_pack.move_ids:
            self.assertEqual(move.state, 'waiting', 'Wrong state of move line.')

        # Check incoming shipment move lines state.
        for move in picking_out.move_ids:
            self.assertEqual(move.state, 'draft', 'Wrong state of move line.')
        # Confirm incoming shipment.
        picking_out.action_confirm()
        # Check incoming shipment move lines state.
        for move in picking_out.move_ids:
            self.assertEqual(move.state, 'waiting', 'Wrong state of move line.')

        # Set the quantity for quant in quants])
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             _product_uom, 1                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               