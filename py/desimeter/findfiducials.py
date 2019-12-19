"""
Utility functions to find fiducials in a list of spots given a know pattern of pinholes
"""

import os
import numpy as np
from desiutil.log import get_logger
from astropy.table import Table,Column
from pkg_resources import resource_filename
from scipy.spatial import cKDTree as KDTree

pinholes_table  = None
fiducials_table = None
fiducials_tree  = None

def findfiducials(spots,separation=7.) :
    
    global pinholes_table
    global fiducials_table
    global fiducials_tree
    
    log = get_logger()
    log.info("findfiducials...")
    
    if pinholes_table is None :
        filename = resource_filename('desimeter',"data/pinholes-fvcxy.csv")
        if not os.path.isfile(filename) :
            log.error("cannot find {}".format(filename))
            raise IOError("cannot find {}".format(filename))
        log.info("reading pinholes FVC coords in {}".format(filename))
        pinholes_table = Table.read(filename,format="csv")

        # the central pinhole is always pin_id 1027, but anyways I recheck this ...
        loc=np.unique(pinholes_table["LOCATION"])
        xpix=np.zeros(loc.size)
        ypix=np.zeros(loc.size)
        for j,f in enumerate(loc) :
            ii=(pinholes_table["LOCATION"]==f)
            mx=np.mean(pinholes_table["XPIX"][ii])
            my=np.mean(pinholes_table["YPIX"][ii])
            # keep coordinates of the central pinhole
            k=np.argmin((pinholes_table["XPIX"][ii]-mx)**2+(pinholes_table["YPIX"][ii]-my)**2)
            xpix[j]=pinholes_table["XPIX"][ii][k]
            ypix[j]=pinholes_table["YPIX"][ii][k]
            #print(f,"pinid=",pinholes_table["DOTID"][ii][k])
        
        fiducials_table = Table([loc,xpix,ypix],names=("LOCATION","XPIX","YPIX"))
        
    # find fiducials candidates  
    # select spots with at least two close neighbors (in pixel units)
    xy   = np.array([spots["XPIX"],spots["YPIX"]]).T
    tree = KDTree(xy)
    measured_spots_distances,measured_spots_indices = tree.query(xy,k=4,distance_upper_bound=separation)
    number_of_neighbors = np.sum( measured_spots_distances<separation,axis=1)
    fiducials_candidates_indices = np.where(number_of_neighbors>=3)[0]  # including self, so at least 3 pinholes
    
    # match candidates to known fiducials
    # nearest neighbor
    
    #fiducials_tree  = KDTree(np.array([fiducials_table["XPIX"],fiducials_table["YPIX"]]).T)
    #xy   = np.array([spots["XPIX"][fiducials_candidates],spots["YPIX"][fiducials_candidates]]).T

    fiducials_tree  = KDTree(np.array([spots["XPIX"][fiducials_candidates_indices],spots["YPIX"][fiducials_candidates_indices]]).T)
    xy   = np.array([fiducials_table["XPIX"],fiducials_table["YPIX"]]).T

    distances,indices = fiducials_tree.query(xy,k=1)
    log.debug("0- median distance = {:4.2f} pixels for {} candidate fiducials and {} known fiducials".format(np.median(distances),fiducials_candidates_indices.size,fiducials_table["XPIX"].size))
    
    # fit offset
    dx = np.median(fiducials_table["XPIX"]-spots["XPIX"][fiducials_candidates_indices][indices])
    dy = np.median(fiducials_table["YPIX"]-spots["YPIX"][fiducials_candidates_indices][indices])
    
    # rematch
    distances,indices = fiducials_tree.query(np.array([fiducials_table["XPIX"]-dx,fiducials_table["YPIX"]-dy]).T,k=1)
    log.debug("1- median distance = {:4.2f} pixels for {} candidate fiducials and {} known fiducials".format(np.median(distances),fiducials_candidates_indices.size,fiducials_table["XPIX"].size))
    rms = 1.48*np.median(distances)
    # print(indices)
    
    maxdistance = np.sqrt((3*rms)**2+2.**2) # keep fiducials within 3 sigma + systematic of 2 pixels
    log.debug("max distance = {} pixel".format(maxdistance))

    selection = np.where(distances<maxdistance)[0]
    
    fiducials_candidates_indices     = fiducials_candidates_indices[indices][selection]
    matching_known_fiducials_indices = selection
    
    log.debug("2- mean distance = {:4.2f} pixels for {} matched fiducials and {} known fiducials".format(np.mean(distances[distances<maxdistance]),fiducials_candidates_indices.size,fiducials_table["XPIX"].size))
    
    
    
    #import matplotlib.pyplot as plt
    #plt.hist(distances[distances<maxdistance],bins=100)
    #plt.figure()
    #plt.plot(spots["XPIX"],spots["YPIX"],".")
    #plt.plot(spots["XPIX"][fiducials_candidates],spots["YPIX"][fiducials_candidates],"o")
    #plt.plot(fiducials_table["XPIX"]-dx,fiducials_table["YPIX"]-dy,"X",color="red")
    #plt.show()

    
    # now, identify pinholes

    nspots=spots["XPIX"].size
    if 'LOCATION' not in spots.dtype.names :
        spots.add_column(Column(np.zeros(nspots,dtype=int)),name='LOCATION')
    if 'DOTID' not in spots.dtype.names :
        spots.add_column(Column(np.zeros(nspots,dtype=int)),name='DOTID')
    
    
    for index1,index2 in zip ( fiducials_candidates_indices , matching_known_fiducials_indices ) :
        pinholes_index1 = measured_spots_indices[index1][measured_spots_distances[index1]<separation]
        pinholes_index2 = np.where(pinholes_table["LOCATION"]==fiducials_table["LOCATION"][index2])[0]

        dx=spots["XPIX"][index1]-fiducials_table["XPIX"][index2]
        dy=spots["YPIX"][index1]-fiducials_table["YPIX"][index2]

        xy_metro = np.array([pinholes_table["XPIX"][pinholes_index2]+dx,pinholes_table["YPIX"][pinholes_index2]+dy]).T
        metrology_tree = KDTree(xy_metro)
        xy_meas  = np.array([spots["XPIX"][pinholes_index1],spots["YPIX"][pinholes_index1]]).T
        distances,matched_indices = metrology_tree.query(xy_meas,k=1)

        if True : # median offset and then rematch
            dx = np.median( spots["XPIX"][pinholes_index1] - pinholes_table["XPIX"][pinholes_index2][matched_indices] )
            dy = np.median( spots["YPIX"][pinholes_index1] - pinholes_table["YPIX"][pinholes_index2][matched_indices] )
            xy_metro = np.array([pinholes_table["XPIX"][pinholes_index2]+dx,pinholes_table["YPIX"][pinholes_index2]+dy]).T
            metrology_tree = KDTree(xy_metro)
            distances,matched_indices = metrology_tree.query(xy_meas,k=1)

        spots["LOCATION"][pinholes_index1] = fiducials_table["LOCATION"][index2]
        spots["DOTID"][pinholes_index1] = pinholes_table["DOTID"][pinholes_index2][matched_indices]
        
    
    return spots