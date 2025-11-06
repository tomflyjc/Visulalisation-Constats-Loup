# (c) JC BAUDIN 2025
__author__ = 'Jean-Christophe Baudin'
__date__ = '2025-10-17'
__copyright__ = '(C) 2025 by Jean-Christophe Baudin'

def classFactory(iface):
    from .main_visualisation_constats import MainPluginVisualisationConstatsLoup  
    return MainPluginVisualisationConstatsLoup(iface)