import sys
sys.path.append('C:/Users/natha/Documents/GitHub/panels')
# sys.path.append('..\\..')
import os
os.chdir('C:/Users/natha/Documents/GitHub/panels/tests/multidomain')

import numpy as np
from structsolve import solve
from structsolve.sparseutils import finalize_symmetric_matrix
import time
import scipy

from panels import Shell
from panels.multidomain.connections import calc_ku_kv_kw_point_pd
from panels.multidomain.connections import fkCpd, fkCld_xcte, fkCld_ycte
from panels.plot_shell import plot_shell
from panels.multidomain import MultiDomain

# Open images
from matplotlib import image as img

from matplotlib import pyplot as plt
import matplotlib.animation as animation
from mpl_toolkits.axes_grid1.inset_locator import mark_inset, zoomed_inset_axes

# To generate mp4's
import matplotlib
matplotlib.rcParams['animation.ffmpeg_path'] = r'C:\Users\natha\Downloads\ffmpeg-2024-04-01\ffmpeg\bin\ffmpeg.exe'

# Printing with reduced no of points (ease of viewing) - Suppress this to print in scientific notations and restart the kernel
np.set_printoptions(formatter={'float': lambda x: "{0:0.2f}".format(x)})

# Modified Newton-Raphson method
def scaling(vec, D):
    """
        A. Peano and R. Riccioni, Automated discretisatton error
        control in finite element analysis. In Finite Elements m
        the Commercial Enviror&ent (Editei by J. 26.  Robinson),
        pp. 368-387. Robinson & Assoc., Verwood.  England (1978)
    """
    non_nulls = ~np.isclose(D, 0)
    vec = vec[non_nulls]
    D = D[non_nulls]
    return np.sqrt((vec*np.abs(1/D))@vec)

# import os
# os.chdir('C:/Users/natha/Documents/GitHub/panels/tests/multidomain')

def img_popup(filename, plot_no = None, title = None):
    '''
    plot_no = current plot no 
    '''
    
    # To open pop up images - Ignore the syntax warning :)
    # %matplotlib qt 
    # For inline images
    # %matplotlib inline
     
    image = img.imread(filename)
    if plot_no is None:
        if title is None:
            plt.title(filename)
        else:
            plt.title(title)
        plt.imshow(image)
        plt.show()
    else:
        if title is None:
            plt.subplot(1,2,plot_no).set_title(filename)
        else:
            plt.subplot(1,2,plot_no).set_title(title)
        plt.imshow(image)
      
        
def convergence():
    i = 0 
    final_res = np.zeros((26,2))
    for no_terms in range(5,31):
        final_res[i,0] = test_dcb_vs_fem(2, no_terms)
        print('------------------------------------')
        final_res[i,1] = test_dcb_vs_fem(3, no_terms)
        print('====================================')
        i += 1
    plt.figure()
    plt.plot(range(5,31), final_res[:,0], label = '2 panels' )
    plt.plot(range(5,31), final_res[:,1], label = '3 panels')
    plt.legend()
    plt.grid()
    plt.title('80 Plies - Clamped')
    plt.xlabel('No of terms in shape function')
    plt.ylabel('w [mm]')
    plt.yticks(np.arange(np.min(final_res), np.max(final_res), 0.01))
    # plt.ylim([np.min(final_res), np.max(final_res)])
    plt.show()

def monotonicity_check_dmg_index(dmg_index):
    # count = 1
    # plt.figure(figsize=(10,10))
    # for i in range(16,24):
    #     check_dmg_index = dmg_index[:,i,8:-1]
    #     plt.subplot(4,2,count)
    #     plt.contourf(check_dmg_index)
    #     count += 1
    #     plt.colorbar()
    # plt.show()

    count = 1
    monotonicity = np.zeros((np.shape(dmg_index)[0], np.shape(dmg_index)[1]), dtype= bool)
    for i in range(np.shape(dmg_index)[1]):
        check_dmg_index = dmg_index[:,i,:]
        monotonicity[:,i] = np.all(check_dmg_index[:, 1:] >= check_dmg_index[:, :-1], axis=1)


def test_dcb_non_linear(no_pan, no_terms, plies):

    '''
        An attempt to recreate the linear case of applying an out of plane tip displacement to a DCB
        using a non-linear solution method
            
        All units in MPa, N, mm
    '''    
    
    # Properties
    E1 = (138300. + 128000.)/2. # MPa
    E2 = (10400. + 11500.)/2. # MPa
    G12 = 5190. # MPa
    nu12 = 0.316
    ply_thickness = 0.14 # mm

    # Plate dimensions (overall)
    a = 225 # mm
    b = 25  # mm
    # Dimensions of panel 1 and 2
    a1 = 0.5*a
    a2 = 0.3*a

    #others
    m = no_terms
    n = no_terms
    # print(f'no terms : {m}')

    simple_layup = [+45, -45]*plies + [0, 90]*plies
    # simple_layup = [0, 0]*10 + [0, 0]*10
    simple_layup += simple_layup[::-1]
    # simple_layup += simple_layup[::-1]
    print('plies ',np.shape(simple_layup)[0])

    laminaprop = (E1, E2, nu12, G12, G12, G12)
     
    # Top DCB panels
    top1 = Shell(group='top', x0=0, y0=0, a=a1, b=b, m=m, n=n, plyt=ply_thickness, stack=simple_layup, laminaprop=laminaprop)
    if no_pan == 2:
        top2 = Shell(group='top', x0=a1, y0=0, a=a-a1, b=b, m=m, n=n, plyt=ply_thickness, stack=simple_layup, laminaprop=laminaprop)
    if no_pan == 3:
        top2 = Shell(group='top', x0=a1, y0=0, a=a2, b=b, m=m, n=n, plyt=ply_thickness, stack=simple_layup, laminaprop=laminaprop)
        top3 = Shell(group='top', x0=a1+a2, y0=0, a=a-a1-a2, b=b, m=m, n=n, plyt=ply_thickness, stack=simple_layup, laminaprop=laminaprop)
    # Bottom DCB panels
    bot1 = Shell(group='bot', x0=0, y0=0, a=a1, b=b, m=m, n=n, plyt=ply_thickness, stack=simple_layup, laminaprop=laminaprop)
    if no_pan == 2:
        bot2 = Shell(group='bot', x0=a1, y0=0, a=a-a1, b=b, m=m, n=n, plyt=ply_thickness, stack=simple_layup, laminaprop=laminaprop)
    if no_pan == 3:
        bot2 = Shell(group='bot', x0=a1, y0=0, a=a2, b=b, m=m, n=n, plyt=ply_thickness, stack=simple_layup, laminaprop=laminaprop)
        bot3 = Shell(group='bot', x0=a1+a2, y0=0, a=a-a1-a2, b=b, m=m, n=n, plyt=ply_thickness, stack=simple_layup, laminaprop=laminaprop)
    
    # boundary conditions
    
    BC = 'bot_end_fixed'
    # Possible strs: 'bot_fully_fixed', 'bot_end_fixed'
    
    clamped = True
    ss = False
    
    if clamped:
        bot_r = 0
        bot_t = 0
        top1_x1_wr = 1
    if ss:
        bot_r = 1
        bot_t = 0
        top1_x1_wr = 0
        
    # DCB with only the lower extreme end fixed at the tip. Rest free
    if BC == 'bot_end_fixed':
        top1.x1u = 1 ; top1.x1ur = 1 ; top1.x2u = 1 ; top1.x2ur = 1
        top1.x1v = 1 ; top1.x1vr = 1 ; top1.x2v = 1 ; top1.x2vr = 1 
        top1.x1w = 1 ; top1.x1wr = top1_x1_wr ; top1.x2w = 1 ; top1.x2wr = 1 
        top1.y1u = 1 ; top1.y1ur = 1 ; top1.y2u = 1 ; top1.y2ur = 1
        top1.y1v = 1 ; top1.y1vr = 1 ; top1.y2v = 1 ; top1.y2vr = 1
        top1.y1w = 1 ; top1.y1wr = 1 ; top1.y2w = 1 ; top1.y2wr = 1
        
        top2.x1u = 1 ; top2.x1ur = 1 ; top2.x2u = 1 ; top2.x2ur = 1
        top2.x1v = 1 ; top2.x1vr = 1 ; top2.x2v = 1 ; top2.x2vr = 1 
        top2.x1w = 1 ; top2.x1wr = 1 ; top2.x2w = 1 ; top2.x2wr = 1  
        top2.y1u = 1 ; top2.y1ur = 1 ; top2.y2u = 1 ; top2.y2ur = 1
        top2.y1v = 1 ; top2.y1vr = 1 ; top2.y2v = 1 ; top2.y2vr = 1
        top2.y1w = 1 ; top2.y1wr = 1 ; top2.y2w = 1 ; top2.y2wr = 1
        
        if no_pan == 3:
            top3.x1u = 1 ; top3.x1ur = 1 ; top3.x2u = 1 ; top3.x2ur = 1
            top3.x1v = 1 ; top3.x1vr = 1 ; top3.x2v = 1 ; top3.x2vr = 1 
            top3.x1w = 1 ; top3.x1wr = 1 ; top3.x2w = 1 ; top3.x2wr = 1  
            top3.y1u = 1 ; top3.y1ur = 1 ; top3.y2u = 1 ; top3.y2ur = 1
            top3.y1v = 1 ; top3.y1vr = 1 ; top3.y2v = 1 ; top3.y2vr = 1
            top3.y1w = 1 ; top3.y1wr = 1 ; top3.y2w = 1 ; top3.y2wr = 1
    
        # bot1.x1u = 0 ; bot1.x1ur = 0 ; bot1.x2u = 1 ; bot1.x2ur = 1
        # bot1.x1v = 0 ; bot1.x1vr = 0 ; bot1.x2v = 1 ; bot1.x2vr = 1
        # bot1.x1w = 0 ; bot1.x1wr = 0 ; bot1.x2w = 1 ; bot1.x2wr = 1
        # bot1.y1u = 1 ; bot1.y1ur = 1 ; bot1.y2u = 1 ; bot1.y2ur = 1
        # bot1.y1v = 1 ; bot1.y1vr = 1 ; bot1.y2v = 1 ; bot1.y2vr = 1
        # bot1.y1w = 1 ; bot1.y1wr = 1 ; bot1.y2w = 1 ; bot1.y2wr = 1
        
        bot1.x1u = 1 ; bot1.x1ur = 1 ; bot1.x2u = 1 ; bot1.x2ur = 1
        bot1.x1v = 1 ; bot1.x1vr = 1 ; bot1.x2v = 1 ; bot1.x2vr = 1
        bot1.x1w = 1 ; bot1.x1wr = 1 ; bot1.x2w = 1 ; bot1.x2wr = 1
        bot1.y1u = 1 ; bot1.y1ur = 1 ; bot1.y2u = 1 ; bot1.y2ur = 1
        bot1.y1v = 1 ; bot1.y1vr = 1 ; bot1.y2v = 1 ; bot1.y2vr = 1
        bot1.y1w = 1 ; bot1.y1wr = 1 ; bot1.y2w = 1 ; bot1.y2wr = 1
        
        if no_pan == 2:
            bot2.x1u = 1 ; bot2.x1ur = 1 ; bot2.x2u = bot_t ; bot2.x2ur = 1 
            bot2.x1v = 1 ; bot2.x1vr = 1 ; bot2.x2v = bot_t ; bot2.x2vr = 1
            bot2.x1w = 1 ; bot2.x1wr = 1 ; bot2.x2w = bot_t ; bot2.x2wr = bot_r
            bot2.y1u = 1 ; bot2.y1ur = 1 ; bot2.y2u = 1 ; bot2.y2ur = 1
            bot2.y1v = 1 ; bot2.y1vr = 1 ; bot2.y2v = 1 ; bot2.y2vr = 1
            bot2.y1w = 1 ; bot2.y1wr = 1 ; bot2.y2w = 1 ; bot2.y2wr = 1
        
        if no_pan == 3:
            bot2.x1u = 1 ; bot2.x1ur = 1 ; bot2.x2u = 1 ; bot2.x2ur = 1
            bot2.x1v = 1 ; bot2.x1vr = 1 ; bot2.x2v = 1 ; bot2.x2vr = 1 
            bot2.x1w = 1 ; bot2.x1wr = 1 ; bot2.x2w = 1 ; bot2.x2wr = 1 
            bot2.y1u = 1 ; bot2.y1ur = 1 ; bot2.y2u = 1 ; bot2.y2ur = 1
            bot2.y1v = 1 ; bot2.y1vr = 1 ; bot2.y2v = 1 ; bot2.y2vr = 1
            bot2.y1w = 1 ; bot2.y1wr = 1 ; bot2.y2w = 1 ; bot2.y2wr = 1
            
            bot3.x1u = 1 ; bot3.x1ur = 1 ; bot3.x2u = bot_t ; bot3.x2ur = 1 
            bot3.x1v = 1 ; bot3.x1vr = 1 ; bot3.x2v = bot_t ; bot3.x2vr = 1 
            bot3.x1w = 1 ; bot3.x1wr = 1 ; bot3.x2w = bot_t ; bot3.x2wr = bot_r 
            bot3.y1u = 1 ; bot3.y1ur = 1 ; bot3.y2u = 1 ; bot3.y2ur = 1
            bot3.y1v = 1 ; bot3.y1vr = 1 ; bot3.y2v = 1 ; bot3.y2vr = 1
            bot3.y1w = 1 ; bot3.y1wr = 1 ; bot3.y2w = 1 ; bot3.y2wr = 1

    # All connections - list of dict
    if no_pan == 2:
        conn = [
         # skin-skin
         dict(p1=top1, p2=top2, func='SSxcte', xcte1=top1.a, xcte2=0),
         dict(p1=bot1, p2=bot2, func='SSxcte', xcte1=bot1.a, xcte2=0),
         dict(p1=top1, p2=bot1, func='SB'), #'_TSL', tsl_type = 'linear'), 
            # dict(p1=top2, p2=bot2, func='SB_TSL', tsl_type = 'linear')
        ]
    if no_pan == 3:
        conn = [
         # skin-skin
           dict(p1=top1, p2=top2, func='SSxcte', xcte1=top1.a, xcte2=0),
           dict(p1=top2, p2=top3, func='SSxcte', xcte1=top2.a, xcte2=0),
           dict(p1=bot1, p2=bot2, func='SSxcte', xcte1=bot1.a, xcte2=0),
           dict(p1=bot2, p2=bot3, func='SSxcte', xcte1=bot2.a, xcte2=0),
           dict(p1=top1, p2=bot1, func='SB'), #'_TSL', tsl_type = 'linear'), 
            # dict(p1=top2, p2=bot2, func='SB_TSL', tsl_type = 'linear')
        ]
    
    # This determines the positions of each panel's (sub)matrix in the global matrix when made a MD obj below
    # So changing this changes the placements i.e. starting row and col of each
    if no_pan == 2:
        panels = [bot1, bot2, top1, top2]
    if no_pan == 3:
        panels = [bot1, bot2, bot3, top1, top2, top3]

    assy = MultiDomain(panels=panels, conn=conn) # assy is now an object of the MultiDomain class
    # Here the panels (shell objs) are modified -- their starting positions in the global matrix is assigned etc

    # Panel at which the disp is applied
    if no_pan == 2:
        disp_panel = top2
    if no_pan == 3:
        disp_panel = top3
        

    if True:
        ######## THIS SHOULD BE CHANGED LATER PER DISP TYPE ###########################################
        ku, kv, kw = calc_ku_kv_kw_point_pd(disp_panel)

    kT = assy.calc_kT()
    size = kT.shape[0]
        
    # To match the inital increment 
    wp = 0.01   
    
    # --------- IMPROVE THE STARTING GUESS --------------
    if True:
        # Prescribed Displacements
        if True:
            disp_type = 'line_xcte' # change based on what's being applied
            
            if disp_type == 'point':
                # Penalty Stiffness
                # Disp in z, so only kw is non zero. ku and kv are zero
                kCp = fkCpd(0., 0., kw, disp_panel, disp_panel.a, disp_panel.b/2, size, disp_panel.row_start, disp_panel.col_start)
                # Point load (added to shell obj)
                disp_panel.add_point_pd(disp_panel.a, disp_panel.b/2, 0., 0., 0., 0., kw, wp)
            if disp_type == 'line_xcte':
                kCp = fkCld_xcte(0., 0., kw, disp_panel, disp_panel.a, size, disp_panel.row_start, disp_panel.col_start)
                disp_panel.add_distr_pd_fixed_x(disp_panel.a, None, None, kw,
                                          funcu=None, funcv=None, funcw = lambda y: wp) #*y/top2.b, cte=True)
            if disp_type == 'line_ycte':
                kCp = fkCld_ycte(0., 0., kw, disp_panel, disp_panel.b, size, disp_panel.row_start, disp_panel.col_start)
                disp_panel.add_distr_pd_fixed_y(disp_panel.b, None, None, kw,
                                          funcu=None, funcv=None, funcw = lambda x: wp) #*x/top2.a, cte=True)
    
        # Stiffness matrix from penalties due to prescribed displacement
        kCp = finalize_symmetric_matrix(kCp)
        
        # Has to be after the forces/loads are added to the panels
        fext = assy.calc_fext()
        
        k0 = kT + kCp
        ci = solve(k0, fext)
        size = k0.shape[0]
    else:
        ci = np.zeros(size) # Only used to calc initial fint
        
    # -------------------- INCREMENTATION --------------------------
    wp_max = 5 # [mm]
    no_iter = 5
    
    # Displacement Incrementation
    for wp in np.linspace(0.01, wp_max, no_iter): 
        print('wp', wp)
    
        # kC = assy.calc_kT(c=ci)
        # size = kC.shape[0]
        
        # Prescribed Displacements
        if True:
            disp_type = 'line_xcte' # change based on what's being applied
            
            # Clears all previously added displs - in NL case, theyre readded so you have 2 disps at the tip
            disp_panel.clear_disps()
            
            if disp_type == 'point':
                # Penalty Stiffness
                # Disp in z, so only kw is non zero. ku and kv are zero
                kCp = fkCpd(0., 0., kw, disp_panel, disp_panel.a, disp_panel.b/2, size, disp_panel.row_start, disp_panel.col_start)
                # Point load (added to shell obj)
                disp_panel.add_point_pd(disp_panel.a, disp_panel.b/2, 0., 0., 0., 0., kw, wp)
            if disp_type == 'line_xcte':
                kCp = fkCld_xcte(0., 0., kw, disp_panel, disp_panel.a, size, disp_panel.row_start, disp_panel.col_start)
                disp_panel.add_distr_pd_fixed_x(disp_panel.a, None, None, kw,
                                           funcu=None, funcv=None, funcw = lambda y: wp) #*y/top2.b, cte=True)
            if disp_type == 'line_ycte':
                kCp = fkCld_ycte(0., 0., kw, disp_panel, disp_panel.b, size, disp_panel.row_start, disp_panel.col_start)
                disp_panel.add_distr_pd_fixed_y(disp_panel.b, None, None, kw,
                                           funcu=None, funcv=None, funcw = lambda x: wp) #*x/top2.a, cte=True)

        # Stiffness matrix from penalties due to prescribed displacement
        kCp = finalize_symmetric_matrix(kCp)
        
        # Has to be after the forces/loads are added to the panels
        fext = assy.calc_fext()

        # Tangent (complete) stiffness matrix
        k0 = kT + kCp
        
        # Inital guess ci and increment dc (same size as fext)
        dc = np.zeros_like(fext)
        
        # Inital fint (0 bec c=0)
        fint = assy.calc_fint(c=ci)
        Ri = fint - fext + kCp*ci
        
        epsilon = 1.e-8 # Convergence criteria
        D = k0.diagonal() # For convergence - calc at beginning of load increment
        
        count = 0 # Tracks number of NR iterations 
        # ignore = False
        
        # Modified Newton Raphson Iteration
        while True:
            dc = solve(k0, -Ri, silent=True)
            
            # Helps initial guess be closer to what it should be
            # if np.isclose(np.linalg.norm(fext)/np.linalg.norm(fint), 0.8):
            #     ignore = True
            # if not ignore:
                # if np.linalg.norm(fext)/np.linalg.norm(fint) > 1000: #and np.linalg.norm(c)/np.linalg.norm(c_org) < 100:
                #     dc = 10*dc
                # elif np.linalg.norm(fext)/np.linalg.norm(fint) > 100: #and np.linalg.norm(c)/np.linalg.norm(c_org) < 100:
                #     dc = 1.5*dc
            
            c = ci + dc
            fint = np.asarray(assy.calc_fint(c=c))
            Ri = fint - fext + kCp*c
            # print(f'Ri {np.linalg.norm(Ri)}')
            crisfield_test = scaling(Ri, D)/max(scaling(fext, D), scaling(fint, D))
            if crisfield_test < epsilon:
                print(f'         Ri {np.linalg.norm(Ri)}')
                # print()
                break
            # print(crisfield_test)
            # print()
            count += 1
            kT = assy.calc_kT(c=c) 
            # print(f'kC {np.max(kC)}')
            k0 = kT + kCp
            ci = c.copy()
            if count > 500:
                # break
                raise RuntimeError('NR not converged :(')
            # Break loop for diverging results
            # if np.linalg.norm(fint)/np.linalg.norm(fext) > 1.5: 
            #     break
        
    c0 = c.copy()

    # ------------------ RESULTS AND POST PROCESSING --------------------
    
    generate_plots = True
    
    # Plotting results
    if True:
        for vec in ['w', 'Mxx']:#, 'Myy', 'Mxy']:#, 'Nxx', 'Nyy']:
            res_bot = assy.calc_results(c=c0, group='bot', vec=vec, no_x_gauss=None, no_y_gauss=None)
            res_top = assy.calc_results(c=c0, group='top', vec=vec, no_x_gauss=None, no_y_gauss=None)
            vecmin = min(np.min(np.array(res_top[vec])), np.min(np.array(res_bot[vec])))
            vecmax = max(np.max(np.array(res_top[vec])), np.max(np.array(res_bot[vec])))
            if vec != 'w':
                print(f'{vec} :: {vecmin:.3f}  {vecmax:.3f}')
            # if vec == 'w':
            if True:
                # Printing max min per panel
                if False:
                    for pan in range(0,np.shape(res_bot[vec])[0]):
                        print(f'{vec} top{pan+1} :: {np.min(np.array(res_top[vec][pan])):.3f}  {np.max(np.array(res_top[vec][pan])):.3f}')
                    print('------------------------------')
                    for pan in range(0,np.shape(res_bot[vec])[0]): 
                        print(f'{vec} bot{pan+1} :: {np.min(np.array(res_bot[vec][pan])):.3f}  {np.max(np.array(res_bot[vec][pan])):.3f}')
                    print('------------------------------')
                print(f'Global TOP {vec} :: {np.min(np.array(res_top[vec])):.3f}  {np.max(np.array(res_top[vec])):.3f}')
                print(f'Global BOT {vec} :: {np.min(np.array(res_bot[vec])):.3f}  {np.max(np.array(res_bot[vec])):.3f}')
                # print(res_bot[vec][1][:,-1]) # disp at the tip
                final_res = np.min(np.array(res_top[vec]))
            
            if generate_plots:
                # if vec == 'w':
                if True:
                    assy.plot(c=c0, group='bot', vec=vec, filename='test_dcb_before_opening_bot_tsl.png', show_boundaries=True,
                                                colorbar=True, res = res_bot, vecmax=vecmax, vecmin=vecmin, display_zero=True)
                    
                    assy.plot(c=c0, group='top', vec=vec, filename='test_dcb_before_opening_top_tsl.png', show_boundaries=True,
                                              colorbar=True, res = res_top, vecmax=vecmax, vecmin=vecmin, display_zero=True)
            
            # Open images
            if generate_plots:
                img_popup('test_dcb_before_opening_top_tsl.png',1, f"{vec} top")
                img_popup('test_dcb_before_opening_bot_tsl.png',2, f"{vec} bot")
                plt.show()
    
    # Test for force
    # Panel at which the disp is applied
    if no_pan == 2:
        force_panel = top2
    if no_pan == 3:
        force_panel = top3
    if False:
        vec = 'Fxx'
        res_bot = assy.calc_results(c=c0, group='bot', vec=vec, no_x_gauss=50, no_y_gauss=60,
                                eval_panel=force_panel, x_cte_force=force_panel.a)
        print(res_bot)
    
        
    return final_res


def test_kCconn_SB_damage(no_pan, no_terms, plies):
    
    '''
        WORKING CORRECTLY:
            
        Tests if the kCSB_dmg stiffness matrix is correct
            Done by testing kCSB_dmg with a uniform kt which is the same as kCSB - both should match
            Run kCSB_dmg with initial stiffness = kt and modify get_kC_conn in MD class to prevent 
                damamge from being calc
                To recreate it, add the following:
                    kt, kr = connections.calc_kt_kr(pA, pB, 'bot-top')
                    kw_tsl = kt*np.ones((no_y_gauss, no_x_gauss))
                If statements need to be changed to allow SB_TSL to be called when no c is passed
            
    '''
    
    # Properties
    E1 = (138300. + 128000.)/2. # MPa
    E2 = (10400. + 11500.)/2. # MPa
    G12 = 5190. # MPa
    nu12 = 0.316
    ply_thickness = 0.14 # mm

    # Plate dimensions (overall)
    a = 225 # mm
    b = 25  # mm
    # Dimensions of panel 1 and 2
    a1 = 0.5*a
    a2 = 0.3*a

    #others
    m = no_terms
    n = no_terms
    # print(f'no terms : {m}')

    simple_layup = [+45, -45]*plies + [0, 90]*plies
    # simple_layup = [0, 0]*10 + [0, 0]*10
    simple_layup += simple_layup[::-1]
    # simple_layup += simple_layup[::-1]
    print('plies ',np.shape(simple_layup)[0])

    laminaprop = (E1, E2, nu12, G12, G12, G12)
     
    # Top DCB panels
    top1 = Shell(group='top', x0=0, y0=0, a=a1, b=b, m=m, n=n, plyt=ply_thickness, stack=simple_layup, laminaprop=laminaprop)
    # Bottom DCB panels
    bot1 = Shell(group='bot', x0=0, y0=0, a=a1, b=b, m=m, n=n, plyt=ply_thickness, stack=simple_layup, laminaprop=laminaprop)

    clamped = True
    ss = False
    
    if clamped:
        bot_r = 0
        bot_t = 0
        top1_x1_wr = 1
    if ss:
        bot_r = 1
        bot_t = 0
        top1_x1_wr = 0
        
    top1.x1u = 1 ; top1.x1ur = 1 ; top1.x2u = 1 ; top1.x2ur = 1
    top1.x1v = 1 ; top1.x1vr = 1 ; top1.x2v = 1 ; top1.x2vr = 1 
    top1.x1w = 1 ; top1.x1wr = top1_x1_wr ; top1.x2w = 1 ; top1.x2wr = 1 
    top1.y1u = 1 ; top1.y1ur = 1 ; top1.y2u = 1 ; top1.y2ur = 1
    top1.y1v = 1 ; top1.y1vr = 1 ; top1.y2v = 1 ; top1.y2vr = 1
    top1.y1w = 1 ; top1.y1wr = 1 ; top1.y2w = 1 ; top1.y2wr = 1
        
    bot1.x1u = 1 ; bot1.x1ur = 1 ; bot1.x2u = 1 ; bot1.x2ur = 1
    bot1.x1v = 1 ; bot1.x1vr = 1 ; bot1.x2v = 1 ; bot1.x2vr = 1
    bot1.x1w = 1 ; bot1.x1wr = 1 ; bot1.x2w = 1 ; bot1.x2wr = 1
    bot1.y1u = 1 ; bot1.y1ur = 1 ; bot1.y2u = 1 ; bot1.y2ur = 1
    bot1.y1v = 1 ; bot1.y1vr = 1 ; bot1.y2v = 1 ; bot1.y2vr = 1
    bot1.y1w = 1 ; bot1.y1wr = 1 ; bot1.y2w = 1 ; bot1.y2wr = 1
    
    panels = [top1, bot1]
    
    conn_org = [dict(p1=top1, p2=bot1, func='SB')]
    assy_org = MultiDomain(panels=panels, conn=conn_org)
    kC_org = assy_org.get_kC_conn(conn=conn_org)
    
    conn_dmg = [dict(p1=top1, p2=bot1, func='SB_TSL', tsl_type = 'bilinear', no_x_gauss=20, no_y_gauss=20)]
    assy_dmg = MultiDomain(panels=panels, conn=conn_dmg)
    kC_dmg = assy_dmg.get_kC_conn(conn=conn_dmg)
    
    # print(kC_org)
    print(np.max(kC_org-kC_dmg))
    

def test_kw_tsl(no_pan, no_terms, plies):
    '''
        Test to see if the damaged stiffness in the TSL works
    '''
    # Properties
    E1 = (138300. + 128000.)/2. # MPa
    E2 = (10400. + 11500.)/2. # MPa
    G12 = 5190. # MPa
    nu12 = 0.316
    ply_thickness = 0.14 # mm

    # Plate dimensions (overall)
    a = 225 # mm
    b = 25  # mm
    # Dimensions of panel 1 and 2
    a1 = 0.5*a
    a2 = 0.3*a

    #others
    m = no_terms
    n = no_terms
    # print(f'no terms : {m}')

    simple_layup = [+45, -45]*plies + [0, 90]*plies
    # simple_layup = [0, 0]*10 + [0, 0]*10
    simple_layup += simple_layup[::-1]
    # simple_layup += simple_layup[::-1]
    print('plies ',np.shape(simple_layup)[0])

    laminaprop = (E1, E2, nu12, G12, G12, G12)
     
    # Top DCB panels
    top1 = Shell(group='top', x0=0, y0=0, a=a1, b=b, m=m, n=n, plyt=ply_thickness, stack=simple_layup, laminaprop=laminaprop)
    # Bottom DCB panels
    bot1 = Shell(group='bot', x0=0, y0=0, a=a1, b=b, m=m, n=n, plyt=ply_thickness, stack=simple_layup, laminaprop=laminaprop)

    import sys
    sys.path.append('C:/Users/natha/Documents/GitHub/panels')
    from panels.multidomain import connections
    del_d = 0.0008*np.ones((15, 4)) # Should all be ki
    del_d[2,3] = 1 # should be 0
    del_d[12,0] = 0.09999 # Should be close to 0
    del_d[12,3] = 0 # Should be ki
    del_d[12,2] = -0.2 # Should be high (k_penalty)
    kw_tsl, dmg_index = connections.calc_kw_tsl(pA=top1, pB=bot1, tsl_type='bilinear', del_d=del_d)
    
    return kw_tsl, dmg_index

def test_tsl(no_terms, plies):
    '''
        Test to see if the damaged stiffness in the TSL works
    '''
    # Properties
    E1 = (138300. + 128000.)/2. # MPa
    E2 = (10400. + 11500.)/2. # MPa
    G12 = 5190. # MPa
    nu12 = 0.316
    ply_thickness = 0.14 # mm

    # Plate dimensions (overall)
    a = 225 # mm
    b = 25  # mm
    # Dimensions of panel 1 and 2
    a1 = 0.5*a
    a2 = 0.3*a

    #others
    m = no_terms
    n = no_terms
    # print(f'no terms : {m}')

    simple_layup = [+45, -45]*plies + [0, 90]*plies
    # simple_layup = [0, 0]*10 + [0, 0]*10
    simple_layup += simple_layup[::-1]
    # simple_layup += simple_layup[::-1]
    print('plies ',np.shape(simple_layup)[0])

    laminaprop = (E1, E2, nu12, G12, G12, G12)
     
    # Top DCB panels
    top1 = Shell(group='top', x0=0, y0=0, a=a1, b=b, m=m, n=n, plyt=ply_thickness, stack=simple_layup, laminaprop=laminaprop)
    # Bottom DCB panels
    bot1 = Shell(group='bot', x0=0, y0=0, a=a1, b=b, m=m, n=n, plyt=ply_thickness, stack=simple_layup, laminaprop=laminaprop)

    import sys
    sys.path.append('C:/Users/natha/Documents/GitHub/panels')
    from panels.multidomain import connections
    del_d = np.linspace(0, 0.03, 100000)
    kw_tsl, dmg_index = connections.calc_kw_tsl(pA=top1, pB=bot1, tsl_type='bilinear', del_d=del_d)
    tau = np.multiply(kw_tsl, del_d)
    
    if True:
        plt.plot(del_d, dmg_index)
        plt.plot(np.array([8.7e-05,8.7e-05]), np.array([0,1]), label='del_o')
        plt.plot(np.array([0.02574712,0.02574712]), np.array([0,1]), label='del_f')
        plt.xlim(0.5e-04,1e-04)
        plt.legend()
    
    if False:
        plt.figure(figsize=(10,8))
        plt.subplot(3,1,1)
        plt.plot(del_d, tau, label='TSL')
        plt.plot(np.array([8.7e-05,8.7e-05]), np.array([0,87]), label='del_o')
        plt.plot(np.array([0.02574712,0.02574712]), np.array([0,87]), label='del_f')
        plt.grid()
        plt.legend()
        plt.subplot(3,1,2)
        plt.plot(del_d, tau, label='TSL')
        plt.plot(np.array([8.7e-05,8.7e-05]), np.array([0,87]), label='del_o')
        plt.plot(np.array([0.02574712,0.02574712]), np.array([0,87]), label='del_f')
        plt.xlim(0.5e-04,1e-04)
        plt.grid()
        plt.legend()
        plt.subplot(3,1,3)
        plt.plot(del_d, tau, label='TSL')
        plt.plot(np.array([8.7e-05,8.7e-05]), np.array([0,87]), label='del_o')
        plt.plot(np.array([0.02574712,0.02574712]), np.array([0,87]), label='del_f')
        plt.xlim(0.0257,0.0258)
        plt.ylim(0,0.5)
        plt.grid()
        plt.legend()
    if False:
        fig, ax = plt.subplots(nrows=1, ncols=1, figsize=(8,5))
        plt.subplot(1,1,1)
        plt.plot(del_d, tau, label='TSL')
        plt.plot(np.array([8.7e-05,8.7e-05]), np.array([0,87]), label='del_o')
        plt.plot(np.array([0.02574712,0.02574712]), np.array([0,87]), label='del_f')
        plt.grid()
        plt.legend()
        
        # Zoomed in for del_f
        ax_zoomed = zoomed_inset_axes(ax, zoom=50, loc='center right')
        ax_zoomed.plot(del_d, tau, label='TSL')
        ax_zoomed.plot(np.array([8.7e-05,8.7e-05]), np.array([0,87]), label='del_o')
        ax_zoomed.plot(np.array([0.02574712,0.02574712]), np.array([0,87]), label='del_f')
        ax_zoomed.yaxis.set_visible(False)
        ax_zoomed.xaxis.set_visible(False)
        ax_zoomed.set(xlim=[0.0257,0.0258], ylim=[0,0.5])
        
        # fix the number of ticks on the inset axes
        ax_zoomed.yaxis.get_major_locator().set_params(nbins=7)
        ax_zoomed.xaxis.get_major_locator().set_params(nbins=7)
        ax_zoomed.tick_params(labelleft=False, labelbottom=False)
        
        # draw a bbox of the region of the inset axes in the parent axes and
        # connecting lines between the bbox and the inset axes area
        mark_inset(ax, ax_zoomed, loc1=2, loc2=4, fc="none", ec="0.5")
        
        
        # Zoomed in for del_o
        ax_zoomed_2 = zoomed_inset_axes(ax, zoom=20000, loc='upper center')
        ax_zoomed_2.plot(del_d, tau, label='TSL')
        ax_zoomed_2.plot(np.array([8.7e-05,8.7e-05]), np.array([0,87]), label='del_o')
        ax_zoomed_2.plot(np.array([0.02574712,0.02574712]), np.array([0,87]), label='del_f')
        ax_zoomed_2.yaxis.set_visible(False)
        ax_zoomed_2.xaxis.set_visible(False)
        ax_zoomed_2.set(xlim=[0.868e-04,0.875e-04], ylim=[86.9995,87.0005])
        
        # fix the number of ticks on the inset axes
        ax_zoomed_2.yaxis.get_major_locator().set_params(nbins=7)
        ax_zoomed_2.xaxis.get_major_locator().set_params(nbins=7)
        ax_zoomed_2.tick_params(labelleft=False, labelbottom=False)
        
        # draw a bbox of the region of the inset axes in the parent axes and
        # connecting lines between the bbox and the inset axes area
        mark_inset(ax, ax_zoomed_2, loc1=2, loc2=3, fc="none", ec="0.5")
        
        plt.show()
    
    
    return kw_tsl, dmg_index
    

def test_dcb_damage_prop(no_terms, plies, filename=''):

    '''
        Damage propagation from a DCB with a precrack
        
        Code for 2 panels might not be right
            
        All units in MPa, N, mm
    '''    
    
    # Properties
    E1 = (138300. + 128000.)/2. # MPa
    E2 = (10400. + 11500.)/2. # MPa
    G12 = 5190. # MPa
    nu12 = 0.316
    ply_thickness = 0.14 # mm

    # Plate dimensions (overall)
    a = 100 # mm
    b = 25  # mm
    # Dimensions of panel 1 and 2
    a1 = 52
    a2 = 0.015

    #others
    m_tsl = no_terms
    n_tsl = no_terms
    m = 6
    n = 6
    # print(f'no terms : {m}')

    simple_layup = [0]*plies
    # simple_layup += simple_layup[::-1]
    # print('plies ',np.shape(simple_layup)[0])

    laminaprop = (E1, E2, nu12, G12, G12, G12)
    
    no_pan = 3
    
    # Top DCB panels
    top1 = Shell(group='top', x0=0, y0=0, a=a1, b=b, m=m_tsl, n=n_tsl, plyt=ply_thickness, stack=simple_layup, laminaprop=laminaprop)
    if no_pan == 2:
        top2 = Shell(group='top', x0=a1, y0=0, a=a-a1, b=b, m=m, n=n, plyt=ply_thickness, stack=simple_layup, laminaprop=laminaprop)
    if no_pan == 3:
        top2 = Shell(group='top', x0=a1, y0=0, a=a2, b=b, m=m, n=n, plyt=ply_thickness, stack=simple_layup, laminaprop=laminaprop)
        top3 = Shell(group='top', x0=a1+a2, y0=0, a=a-a1-a2, b=b, m=m, n=n, plyt=ply_thickness, stack=simple_layup, laminaprop=laminaprop)
    # Bottom DCB panels
    bot1 = Shell(group='bot', x0=0, y0=0, a=a1, b=b, m=m_tsl, n=n_tsl, plyt=ply_thickness, stack=simple_layup, laminaprop=laminaprop)
    if no_pan == 2:
        bot2 = Shell(group='bot', x0=a1, y0=0, a=a-a1, b=b, m=m, n=n, plyt=ply_thickness, stack=simple_layup, laminaprop=laminaprop)
    if no_pan == 3:
        bot2 = Shell(group='bot', x0=a1, y0=0, a=a2, b=b, m=m, n=n, plyt=ply_thickness, stack=simple_layup, laminaprop=laminaprop)
        bot3 = Shell(group='bot', x0=a1+a2, y0=0, a=a-a1-a2, b=b, m=m, n=n, plyt=ply_thickness, stack=simple_layup, laminaprop=laminaprop)
    
    # boundary conditions
    
    BC = 'bot_end_fixed'
    # Possible strs: 'bot_fully_fixed', 'bot_end_fixed'
    
    clamped = False
    ss = True
    
    if clamped:
        bot_r = 0
        bot_t = 0
        top1_x1_wr = 1
    if ss:
        bot_r = 1
        bot_t = 0
        top1_x1_wr = 0
        
    # DCB with only the lower extreme end fixed at the tip. Rest free
    if BC == 'bot_end_fixed':
        top1.x1u = 1 ; top1.x1ur = 1 ; top1.x2u = 1 ; top1.x2ur = 1
        top1.x1v = 1 ; top1.x1vr = 1 ; top1.x2v = 1 ; top1.x2vr = 1 
        top1.x1w = 1 ; top1.x1wr = top1_x1_wr ; top1.x2w = 1 ; top1.x2wr = 1 
        top1.y1u = 1 ; top1.y1ur = 1 ; top1.y2u = 1 ; top1.y2ur = 1
        top1.y1v = 1 ; top1.y1vr = 1 ; top1.y2v = 1 ; top1.y2vr = 1
        top1.y1w = 1 ; top1.y1wr = 1 ; top1.y2w = 1 ; top1.y2wr = 1
        
        top2.x1u = 1 ; top2.x1ur = 1 ; top2.x2u = 1 ; top2.x2ur = 1
        top2.x1v = 1 ; top2.x1vr = 1 ; top2.x2v = 1 ; top2.x2vr = 1 
        top2.x1w = 1 ; top2.x1wr = 1 ; top2.x2w = 1 ; top2.x2wr = 1  
        top2.y1u = 1 ; top2.y1ur = 1 ; top2.y2u = 1 ; top2.y2ur = 1
        top2.y1v = 1 ; top2.y1vr = 1 ; top2.y2v = 1 ; top2.y2vr = 1
        top2.y1w = 1 ; top2.y1wr = 1 ; top2.y2w = 1 ; top2.y2wr = 1
        
        if no_pan == 3:
            top3.x1u = 1 ; top3.x1ur = 1 ; top3.x2u = 1 ; top3.x2ur = 1
            top3.x1v = 1 ; top3.x1vr = 1 ; top3.x2v = 1 ; top3.x2vr = 1 
            top3.x1w = 1 ; top3.x1wr = 1 ; top3.x2w = 1 ; top3.x2wr = 1  
            top3.y1u = 1 ; top3.y1ur = 1 ; top3.y2u = 1 ; top3.y2ur = 1
            top3.y1v = 1 ; top3.y1vr = 1 ; top3.y2v = 1 ; top3.y2vr = 1
            top3.y1w = 1 ; top3.y1wr = 1 ; top3.y2w = 1 ; top3.y2wr = 1
    
        # bot1.x1u = 0 ; bot1.x1ur = 0 ; bot1.x2u = 1 ; bot1.x2ur = 1
        # bot1.x1v = 0 ; bot1.x1vr = 0 ; bot1.x2v = 1 ; bot1.x2vr = 1
        # bot1.x1w = 0 ; bot1.x1wr = 0 ; bot1.x2w = 1 ; bot1.x2wr = 1
        # bot1.y1u = 1 ; bot1.y1ur = 1 ; bot1.y2u = 1 ; bot1.y2ur = 1
        # bot1.y1v = 1 ; bot1.y1vr = 1 ; bot1.y2v = 1 ; bot1.y2vr = 1
        # bot1.y1w = 1 ; bot1.y1wr = 1 ; bot1.y2w = 1 ; bot1.y2wr = 1
        
        bot1.x1u = 1 ; bot1.x1ur = 1 ; bot1.x2u = 1 ; bot1.x2ur = 1
        bot1.x1v = 1 ; bot1.x1vr = 1 ; bot1.x2v = 1 ; bot1.x2vr = 1
        bot1.x1w = 1 ; bot1.x1wr = 1 ; bot1.x2w = 1 ; bot1.x2wr = 1
        bot1.y1u = 1 ; bot1.y1ur = 1 ; bot1.y2u = 1 ; bot1.y2ur = 1
        bot1.y1v = 1 ; bot1.y1vr = 1 ; bot1.y2v = 1 ; bot1.y2vr = 1
        bot1.y1w = 1 ; bot1.y1wr = 1 ; bot1.y2w = 1 ; bot1.y2wr = 1
        
        if no_pan == 2:
            bot2.x1u = 1 ; bot2.x1ur = 1 ; bot2.x2u = bot_t ; bot2.x2ur = 1 
            bot2.x1v = 1 ; bot2.x1vr = 1 ; bot2.x2v = bot_t ; bot2.x2vr = 1
            bot2.x1w = 1 ; bot2.x1wr = 1 ; bot2.x2w = bot_t ; bot2.x2wr = bot_r
            bot2.y1u = 1 ; bot2.y1ur = 1 ; bot2.y2u = 1 ; bot2.y2ur = 1
            bot2.y1v = 1 ; bot2.y1vr = 1 ; bot2.y2v = 1 ; bot2.y2vr = 1
            bot2.y1w = 1 ; bot2.y1wr = 1 ; bot2.y2w = 1 ; bot2.y2wr = 1
        
        if no_pan == 3:
            bot2.x1u = 1 ; bot2.x1ur = 1 ; bot2.x2u = 1 ; bot2.x2ur = 1
            bot2.x1v = 1 ; bot2.x1vr = 1 ; bot2.x2v = 1 ; bot2.x2vr = 1 
            bot2.x1w = 1 ; bot2.x1wr = 1 ; bot2.x2w = 1 ; bot2.x2wr = 1 
            bot2.y1u = 1 ; bot2.y1ur = 1 ; bot2.y2u = 1 ; bot2.y2ur = 1
            bot2.y1v = 1 ; bot2.y1vr = 1 ; bot2.y2v = 1 ; bot2.y2vr = 1
            bot2.y1w = 1 ; bot2.y1wr = 1 ; bot2.y2w = 1 ; bot2.y2wr = 1
            
            bot3.x1u = 1 ; bot3.x1ur = 1 ; bot3.x2u = bot_t ; bot3.x2ur = 1 
            bot3.x1v = 1 ; bot3.x1vr = 1 ; bot3.x2v = bot_t ; bot3.x2vr = 1 
            bot3.x1w = 1 ; bot3.x1wr = 1 ; bot3.x2w = bot_t ; bot3.x2wr = bot_r 
            bot3.y1u = 1 ; bot3.y1ur = 1 ; bot3.y2u = 1 ; bot3.y2ur = 1
            bot3.y1v = 1 ; bot3.y1vr = 1 ; bot3.y2v = 1 ; bot3.y2vr = 1
            bot3.y1w = 1 ; bot3.y1wr = 1 ; bot3.y2w = 1 ; bot3.y2wr = 1

    # All connections - list of dict
    if no_pan == 2:
        conn = [
         # skin-skin
         dict(p1=top1, p2=top2, func='SSxcte', xcte1=top1.a, xcte2=0),
         dict(p1=bot1, p2=bot2, func='SSxcte', xcte1=bot1.a, xcte2=0),
         dict(p1=top1, p2=bot1, func='SB'), #'_TSL', tsl_type = 'linear'), 
            # dict(p1=top2, p2=bot2, func='SB_TSL', tsl_type = 'linear')
        ]
    if no_pan == 3:
        conn = [
         # skin-skin
           dict(p1=top1, p2=top2, func='SSxcte', xcte1=top1.a, xcte2=0),
           dict(p1=top2, p2=top3, func='SSxcte', xcte1=top2.a, xcte2=0),
           dict(p1=bot1, p2=bot2, func='SSxcte', xcte1=bot1.a, xcte2=0),
           dict(p1=bot2, p2=bot3, func='SSxcte', xcte1=bot2.a, xcte2=0),
           # dict(p1=top1, p2=bot1, func='SB'), #'_TSL', tsl_type = 'linear'), 
           dict(p1=top1, p2=bot1, func='SB_TSL', tsl_type = 'bilinear', no_x_gauss=60, no_y_gauss=30)
        ]
    
    # This determines the positions of each panel's (sub)matrix in the global matrix when made a MD obj below
    # So changing this changes the placements i.e. starting row and col of each
    if no_pan == 2:
        panels = [bot1, bot2, top1, top2]
    if no_pan == 3:
        panels = [bot1, bot2, bot3, top1, top2, top3]

    assy = MultiDomain(panels=panels, conn=conn) # assy is now an object of the MultiDomain class
    # Here the panels (shell objs) are modified -- their starting positions in the global matrix is assigned etc

    # Panel at which the disp is applied
    if no_pan == 2:
        disp_panel = top2
    if no_pan == 3:
        disp_panel = top3
    



    if True:
        ######## THIS SHOULD BE CHANGED LATER PER DISP TYPE ###########################################
        ku, kv, kw = calc_ku_kv_kw_point_pd(disp_panel)
        
    size = assy.get_size()
        
    # To match the inital increment 
    wp = 0.01   
    
    # --------- IMPROVE THE STARTING GUESS --------------
    if False:
        # Prescribed Displacements
        if True:
            disp_type = 'point' # change based on what's being applied
            
            if disp_type == 'point':
                # Penalty Stiffness
                # Disp in z, so only kw is non zero. ku and kv are zero
                kCp = fkCpd(0., 0., kw, disp_panel, disp_panel.a, disp_panel.b/2, size, disp_panel.row_start, disp_panel.col_start)
                # Point load (added to shell obj)
                disp_panel.add_point_pd(disp_panel.a, disp_panel.b/2, 0., 0., 0., 0., kw, wp)
            if disp_type == 'line_xcte':
                kCp = fkCld_xcte(0., 0., kw, disp_panel, disp_panel.a, size, disp_panel.row_start, disp_panel.col_start)
                disp_panel.add_distr_pd_fixed_x(disp_panel.a, None, None, kw,
                                          funcu=None, funcv=None, funcw = lambda y: wp) #*y/top2.b, cte=True)
            if disp_type == 'line_ycte':
                kCp = fkCld_ycte(0., 0., kw, disp_panel, disp_panel.b, size, disp_panel.row_start, disp_panel.col_start)
                disp_panel.add_distr_pd_fixed_y(disp_panel.b, None, None, kw,
                                          funcu=None, funcv=None, funcw = lambda x: wp) #*x/top2.a, cte=True)
    
        # Stiffness matrix from penalties due to prescribed displacement
        kCp = finalize_symmetric_matrix(kCp)
        
        # Has to be after the forces/loads are added to the panels
        fext = assy.calc_fext()
        
        k0 = kT + kCp
        ci = solve(k0, fext)
        size = k0.shape[0]
    else:
        ci = np.zeros(size) # Only used to calc initial fint
        
        
    # -------------------- INCREMENTATION --------------------------
    # wp_max = 10 # [mm]
    # no_iter_disp = 100
    
    disp_iter_no = 0
    
    # Finding info of the connection
    for conn_list in conn:
        if conn_list['func'] == 'SB_TSL':
            no_x_gauss = conn_list['no_x_gauss']
            no_y_gauss = conn_list['no_y_gauss']
            tsl_type = conn_list['tsl_type']
            p_top = conn_list['p1']
            p_bot = conn_list['p2']
            break
        
    # Initilaize mat to store results
    # w_iter = np.unique(np.concatenate((np.linspace(0.01,5,5), np.linspace(5,7,3), np.linspace(7,10,5))))
    # w_iter = np.linspace(0.01,15,100)
    w_iter = np.linspace(0.01,8,100)
    # w_iter = [0.01, 2]
    
    dmg_index = np.zeros((no_y_gauss,no_x_gauss,np.shape(w_iter)[0]))
    del_d = np.zeros((no_y_gauss,no_x_gauss,np.shape(w_iter)[0]))
    kw_tsl = np.zeros((no_y_gauss,no_x_gauss,np.shape(w_iter)[0]))
    force_intgn = np.zeros((np.shape(w_iter)[0], 2))
    displ_top_root = np.zeros((50,200,np.shape(w_iter)[0]))
    displ_bot_root = np.zeros((50,200,np.shape(w_iter)[0]))
    c_all = np.zeros((size, np.shape(w_iter)[0]))
    
    
    # Displacement Incrementation
    for wp in w_iter: 
        print(f'------------ wp = {wp:.3f} ---------------')
        
        # Prescribed Displacements
        if True:
            disp_type = 'line_xcte' # change based on what's being applied
            
            # Clears all previously added displs - otherwise in NL case, theyre readded so you have 2 disps at the tip
            disp_panel.clear_disps()
            
            if disp_type == 'point':
                # Penalty Stiffness
                # Disp in z, so only kw is non zero. ku and kv are zero
                kCp = fkCpd(0., 0., kw, disp_panel, disp_panel.a, disp_panel.b/2, size, disp_panel.row_start, disp_panel.col_start)
                # Point load (added to shell obj)
                disp_panel.add_point_pd(disp_panel.a, disp_panel.b/2, 0., 0., 0., 0., kw, wp)
            if disp_type == 'line_xcte':
                kCp = fkCld_xcte(0., 0., kw, disp_panel, disp_panel.a, size, disp_panel.row_start, disp_panel.col_start)
                disp_panel.add_distr_pd_fixed_x(disp_panel.a, None, None, kw,
                                           funcu=None, funcv=None, funcw = lambda y: wp) #*y/top2.b, cte=True)
            if disp_type == 'line_ycte':
                kCp = fkCld_ycte(0., 0., kw, disp_panel, disp_panel.b, size, disp_panel.row_start, disp_panel.col_start)
                disp_panel.add_distr_pd_fixed_y(disp_panel.b, None, None, kw,
                                           funcu=None, funcv=None, funcw = lambda x: wp) #*x/top2.a, cte=True)

        # Stiffness matrix from penalties due to prescribed displacement
        kCp = finalize_symmetric_matrix(kCp)
        
        # Has to be after the forces/loads are added to the panels
        fext = assy.calc_fext()

        # Inital guess ci and increment dc (same size as fext)
        dc = np.zeros_like(fext)
        
        # Inital fint (0 bec c=0)
        fint = assy.calc_fint(c=ci)
        # Residual with disp terms
        Ri = fint - fext + kCp*ci
        
        if disp_iter_no != 0:
            kT = assy.calc_kT(c=c) 
        if disp_iter_no == 0 and np.max(ci) == 0:
            kT = assy.calc_kT(c=ci)
            k0 = kT + kCp
        
        epsilon = 1.e-7 # Convergence criteria
        D = k0.diagonal() # For convergence - calc at beginning of load increment
        
        count = 0 # Tracks number of NR iterations 

        # Modified Newton Raphson Iteration
        while True:
            # print()
            # print(f"------------ NR start {count+1}--------------")
            dc = solve(k0, -Ri, silent=True)
            c = ci + dc
            
            kC_conn = assy.get_kC_conn(c=c)
            fint = np.asarray(assy.calc_fint(c=c, kC_conn=kC_conn))
            Ri = fint - fext + kCp*c
            # print(f'Ri {np.linalg.norm(Ri)}')
            
            # Extracting data out of the MD class for plotting etc 
                # Damage considerations are already implemented in the Multidomain class functions kT, fint - no need to include anything externally

            # kw_tsl_iter, dmg_index_iter, del_d_iter = assy.calc_k_dmg(c=c, pA=p_top, pB=p_bot, no_x_gauss=no_x_gauss, no_y_gauss=no_y_gauss, tsl_type=tsl_type)
            # print(f"             NR end {count} -- wp={wp:.3f}  max dmg {np.max(dmg_index_iter):.3f}  ---") # min del_d {np.min(del_d_iter):.2e}---------")
            # print(f'    del_d min {np.min(del_d_iter)}  -- max {np.max(del_d_iter):.4f}')
            
            crisfield_test = scaling(Ri, D)/max(scaling(fext, D), scaling(fint, D))
            # print(f'    crisfield {crisfield_test:.4f}')
            if crisfield_test < epsilon:
                break
            
            count += 1
            kT = assy.calc_kT(c=c, kC_conn=kC_conn) 
            k0 = kT + kCp
            ci = c.copy()
            
            if count > 500:
                print('Unconverged Results !!!!!!!!!!!!!!!!!!!')
                return None, dmg_index, del_d, kw_tsl
                raise RuntimeError('NR didnt converged :(') 
        
        
        if hasattr(assy, "del_d"):
            kw_tsl[:,:,disp_iter_no], dmg_index[:,:,disp_iter_no], del_d[:,:,disp_iter_no]  = assy.calc_k_dmg(c=c, pA=p_top, pB=p_bot, 
                                 no_x_gauss=no_x_gauss, no_y_gauss=no_y_gauss, tsl_type=tsl_type, 
                                 prev_max_del_d=assy.del_d)
        else:
            kw_tsl[:,:,disp_iter_no], dmg_index[:,:,disp_iter_no], del_d[:,:,disp_iter_no]  = assy.calc_k_dmg(c=c, pA=p_top, pB=p_bot, 
                                 no_x_gauss=no_x_gauss, no_y_gauss=no_y_gauss, tsl_type=tsl_type,
                                 prev_max_del_d=None)
            
        c_all[:,disp_iter_no] = c
            
        # Update max del_d AFTER a converged NR iteration
        assy.update_max_del_d(curr_max_del_d=del_d[:,:,disp_iter_no])
        
        # kw_tsl[:,:,disp_iter_no], dmg_index[:,:,disp_iter_no], del_d[:,:,disp_iter_no] = assy.calc_k_dmg(c=c, pA=p_top, pB=p_bot, no_x_gauss=no_x_gauss, no_y_gauss=no_y_gauss, tsl_type=tsl_type)
        print(f'                    max dmg_index {np.max(dmg_index[:,:,disp_iter_no]):.4f}')
        # print(f'        max del_d {np.max(del_d[:,:,disp_iter_no])}')
        # print(f'       min del_d {np.min(del_d[:,:,disp_iter_no])}')
        # print(f'        max kw_tsl {np.max(kw_tsl[:,:,disp_iter_no])}')
        
        
        # Force - TEMP - CHECK LATER AND EDIT/REMOVE
        if True:
            force_intgn[disp_iter_no, 0] = wp
            force_intgn[disp_iter_no, 1] = assy.force_out_plane(c, group=None, eval_panel=top3, x_cte_force=None, y_cte_force=None,
                      gridx=100, gridy=50, NLterms=True, no_x_gauss=128, no_y_gauss=128)
        else: 
            force_intgn = None
        
        # Calc displ of top and bottom panels at each increment
        if True:
            res_pan_top = assy.calc_results(c=c, eval_panel=top1, vec='w', 
                                    no_x_gauss=200, no_y_gauss=50)
            res_pan_bot = assy.calc_results(c=c, eval_panel=bot1, vec='w', 
                                    no_x_gauss=200, no_y_gauss=50)
            displ_top_root[:,:,disp_iter_no] = res_pan_top['w'][0]
            displ_bot_root[:,:,disp_iter_no] = res_pan_bot['w'][0]
        else:
            res_pan_top = None
            res_pan_bot = None
        
        disp_iter_no += 1
        print()
        
        if np.all(dmg_index == 1):
            print('Cohesive Zone has failed')
            break
        
        
    # ------------------ SAVING VARIABLES --------------------
    if True:
        np.save(f'{dmg_index}_{filename}', dmg_index)
        np.save(f'{del_d}_{filename}', del_d)
        np.save(f'{kw_tsl}_{filename}', kw_tsl)
        np.save(f'{force_intgn}_{filename}', force_intgn)
        np.save(f'{displ_top_root}_{filename}', displ_top_root)
        np.save(f'{displ_bot_root}_{filename}', displ_bot_root)
        np.save(f'{c_all}_{filename}', c_all)
        
        
    
    # ------------------ RESULTS AND POST PROCESSING --------------------
    
    c0 = c.copy()

    generate_plots = False
    
    final_res = None
    # Plotting results
    if False:
        for vec in ['w']:#, 'Mxx']:#, 'Myy', 'Mxy']:#, 'Nxx', 'Nyy']:
            res_bot = assy.calc_results(c=c0, group='bot', vec=vec, no_x_gauss=None, no_y_gauss=None)
            res_top = assy.calc_results(c=c0, group='top', vec=vec, no_x_gauss=None, no_y_gauss=None)
            vecmin = min(np.min(np.array(res_top[vec])), np.min(np.array(res_bot[vec])))
            vecmax = max(np.max(np.array(res_top[vec])), np.max(np.array(res_bot[vec])))
            if vec != 'w':
                print(f'{vec} :: {vecmin:.3f}  {vecmax:.3f}')
            # if vec == 'w':
            if True:
                # Printing max min per panel
                if False:
                    for pan in range(0,np.shape(res_bot[vec])[0]):
                        print(f'{vec} top{pan+1} :: {np.min(np.array(res_top[vec][pan])):.3f}  {np.max(np.array(res_top[vec][pan])):.3f}')
                    print('------------------------------')
                    for pan in range(0,np.shape(res_bot[vec])[0]): 
                        print(f'{vec} bot{pan+1} :: {np.min(np.array(res_bot[vec][pan])):.3f}  {np.max(np.array(res_bot[vec][pan])):.3f}')
                    print('------------------------------')
                print(f'Global TOP {vec} :: {np.min(np.array(res_top[vec])):.3f}  {np.max(np.array(res_top[vec])):.3f}')
                print(f'Global BOT {vec} :: {np.min(np.array(res_bot[vec])):.3f}  {np.max(np.array(res_bot[vec])):.3f}')
                # print(res_bot[vec][1][:,-1]) # disp at the tip
                final_res = np.min(np.array(res_top[vec]))
            
            if generate_plots:
                # if vec == 'w':
                if True:
                    assy.plot(c=c0, group='bot', vec=vec, filename='test_dcb_before_opening_bot_tsl.png', show_boundaries=True,
                                                colorbar=True, res = res_bot, vecmax=vecmax, vecmin=vecmin, display_zero=True)
                    
                    assy.plot(c=c0, group='top', vec=vec, filename='test_dcb_before_opening_top_tsl.png', show_boundaries=True,
                                              colorbar=True, res = res_top, vecmax=vecmax, vecmin=vecmin, display_zero=True)
            
            # Open images
            if generate_plots:
                img_popup('test_dcb_before_opening_top_tsl.png',1, f"{vec} top")
                img_popup('test_dcb_before_opening_bot_tsl.png',2, f"{vec} bot")
                plt.show()
    
    animate = False
    if animate:    
        def animate(i):
            curr_res = frames[i]
            max_res = np.max(curr_res)
            min_res = np.min(curr_res)
            if animate_var == 'dmg_index':
                if min_res == 0:
                    vmin = 0.0
                    vmax = 1.0
                else: 
                    possible_min_cbar = [0,0.5,0.85,0.9,0.95,0.99]
                    vmin = max(list(filter(lambda x: x<min_res, possible_min_cbar)))
                    vmax = 1.0
            else:
                vmin = min_res
                vmax = max_res
            im = ax.imshow(curr_res)
            fig.colorbar(im, cax=cax)
            im.set_data(curr_res)
            im.set_clim(vmin, vmax)
            tx.set_text(f'{animate_var}     -   Disp={w_iter[i]:.2f} mm')
        
        from mpl_toolkits.axes_grid1 import make_axes_locatable
        
        for animate_var in ["dmg_index", "del_d"]:#, 'kw_tsl']:
            
            fig = plt.figure()
            ax = fig.add_subplot(111)    
            div = make_axes_locatable(ax)
            cax = div.append_axes('right', '5%', '5%')
            
            frames = [] # for storing the generated images
            for i in range(np.shape(locals()[animate_var])[2]):
                frames.append(locals()[animate_var][:,:,i])
                
            cv0 = frames[0]
            im = ax.imshow(cv0) 
            cb = fig.colorbar(im, cax=cax)
            tx = ax.set_title('Frame 0')
                
            ani = animation.FuncAnimation(fig, animate, frames=np.shape(locals()[animate_var])[2],
                                          interval = 200, repeat_delay=1000)
            FFwriter = animation.FFMpegWriter(fps=5)
            ani.save(f'{animate_var}.mp4', writer=FFwriter)
            # ani.save(f'{animate_var}.gif', writer='imagemagick')
        
    return dmg_index, del_d, kw_tsl, force_intgn, displ_top_root, displ_bot_root, c_all




if __name__ == "__main__":
    animate = False
    
    if True:
        if not animate:
            # test_dcb_non_linear(3, 4, 1)
            # kw_tsl, dmg_index = test_kw_tsl(1, 6, 1)
            dmg_index, del_d, kw_tsl, force_intgn, displ_top_root, displ_bot_root, c_all = test_dcb_damage_prop(no_terms=8, plies=15)
            # final_res, dmg_index, del_d, kw_tsl = test_dcb_damage_prop_modified_k(no_terms=10, plies=15)
    
        
        if animate:    
            def animate(i):
                curr_res = frames[i]
                max_res = np.max(curr_res)
                min_res = np.min(curr_res)
                if animate_var == 'dmg_index':
                    if min_res == 0:
                        vmin = 0.0
                        vmax = 1.0
                    else: 
                        possible_min_cbar = [0,0.5,0.85,0.9,0.95,0.99]
                        vmin = max(list(filter(lambda x: x<min_res, possible_min_cbar)))
                        vmax = 1.0
                else:
                    vmin = min_res
                    vmax = max_res
                im = ax.imshow(curr_res)
                fig.colorbar(im, cax=cax)
                im.set_data(curr_res)
                im.set_clim(vmin, vmax)
                tx.set_text(f'{animate_var}     -   Disp={w_iter[i]:.2f} mm')
            
            from mpl_toolkits.axes_grid1 import make_axes_locatable
            
            for animate_var in ["dmg_index", "del_d"]:
                
                fig = plt.figure()
                ax = fig.add_subplot(111)    
                div = make_axes_locatable(ax)
                cax = div.append_axes('right', '5%', '5%')
                
                frames = [] # for storing the generated images
                for i in range(np.shape(locals()[animate_var])[2]):
                    frames.append(locals()[animate_var][:,:,i])
                    
                cv0 = frames[0]
                im = ax.imshow(cv0) 
                cb = fig.colorbar(im, cax=cax)
                tx = ax.set_title('Frame 0')
                    
                ani = animation.FuncAnimation(fig, animate, frames=np.shape(locals()[animate_var])[2],
                                              interval = 200, repeat_delay=1000)
                FFwriter = animation.FFMpegWriter(fps=5)
                ani.save(f'{animate_var}.mp4', writer=FFwriter)
                # ani.save(f'{animate_var}.gif', writer='imagemagick')
                
    # kw_tsl, dmg_index = test_tsl(8, 1)