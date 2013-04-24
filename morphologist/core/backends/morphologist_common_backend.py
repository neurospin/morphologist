from morphologist_common.gui.histo_analysis_widget \
    import load_histo_data, create_histo_view, HistoData
from morphologist_common.gui.histo_analysis_editor import create_histo_editor

from morphologist.core.gui.qt_backend import QtGui
from morphologist.core.backends import Backend
from morphologist.core.backends.mixins import VectorGraphicsManagerMixin


class MorphologistCommonBackend(Backend, VectorGraphicsManagerMixin):
    
    def __init__(self):
        super(MorphologistCommonBackend, self).__init__()

### display
    def create_view(self, parent):
        return create_histo_view(parent)

    def create_extended_view(self, parent):
        view = create_histo_editor()
        view.setParent(parent)
        return view

    def clear_view(self, backend_view):
        backend_view.clear()

    def add_object_in_view(self, backend_object, backend_view):
        backend_view.set_histo_data(backend_object, nbins=100)
        backend_view.draw_histo()

    def set_bgcolor_view(self, backend_view, color):
        palette = QtGui.QPalette(QtGui.QColor(*color))
        backend_view.setPalette(palette)

    def add_object_in_editor(self, backend_object, backend_view):
        if isinstance( backend_object, HistoData ):
            backend_view.set_histo_data(backend_object, nbins=100)
        else:
            backend_view.set_bias_corrected_image( backend_object.fileName() )

### objects loader
    def load_histogram(self, filename):
        return load_histo_data(filename)
