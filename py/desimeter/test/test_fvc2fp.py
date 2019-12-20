"""
Test FVC <-> FP transformation code
"""

import os
import unittest
from pkg_resources import resource_filename

import numpy as np
from astropy.table import Table

from desimeter.transform.fvc2fp.poly2d import FVCFP_Polynomial

class TestFVC2FP(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        cls.spotfile = resource_filename('desimeter', 'test/data/test-spots.csv')

    @classmethod
    def tearDownClass(cls):
        pass

    def test_fit(self):
        tx = FVCFP_Polynomial()
        spots = Table.read(self.spotfile)
        spots_orig = spots.copy()
        
        #- basic fit isn't supposed to modify input
        tx.fit(spots)
        self.assertTrue(spots.colnames == spots_orig.colnames)
        for colname in spots.colnames:
            yep = np.all(spots[colname] == spots_orig[colname])
            self.assertTrue(yep, 'Column {} changed values'.format(colname))

        #- Fitting with a lower degree polynomial
        tx.fit(spots, degree=2)
        
        #- Updating the spots should update XFP,YFP but not XPIX,YPIX
        tx.fit(spots, update_spots=True)
        self.assertTrue(np.all(spots['XPIX'] == spots_orig['XPIX']))
        self.assertTrue(np.all(spots['YPIX'] == spots_orig['YPIX']))
        self.assertFalse(np.all(spots['XFP'] == spots_orig['XFP']))
        self.assertFalse(np.all(spots['YFP'] == spots_orig['YFP']))

    def test_transform(self):
        tx = FVCFP_Polynomial()
        spots = Table.read(self.spotfile)
        tx.fit(spots, update_spots=True)

        #- Transform FVC -> FP should be close to the FP metrology
        ii = (spots['XMETRO']>0) & (spots['YMETRO']>0)
        dx = spots['XFP'][ii] - spots['XMETRO'][ii]
        dy = spots['YFP'][ii] - spots['YMETRO'][ii]
        dr = np.sqrt(dx**2 + dy**2)
        self.assertLess(np.std(dr), 0.02)  #- RMS < 20 microns
        self.assertLess(np.std(dr), 0.03)  #- median < 30 microns
        self.assertLess(np.max(dr), 0.10)  #- worst outlier < 100 microns

        #- make a grid of different spots not used in the fit
        nspots = 20
        xpix = np.random.uniform(500, 5500, nspots)
        ypix = np.random.uniform(500, 5500, nspots)
        xfp, yfp = tx.fvc2fp(xpix, ypix)
        xpix_new, ypix_new = tx.fp2fvc(xfp, yfp)

        #- test roundtrip with close cuts in FVC pixel space
        dr = np.sqrt((xpix - xpix_new)**2 + (ypix - ypix_new)**2)
        self.assertLess(np.std(dr), 0.05)
        self.assertLess(np.std(dr), 0.10)
        self.assertLess(np.max(dr), 0.20)
        
if __name__ == '__main__':
    unittest.main()
        