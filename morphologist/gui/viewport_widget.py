import os

from morphologist.backends import Backend
from .qt_backend import QtCore, QtGui, loadUi 
from morphologist.gui import ui_directory 


class SubjectwiseViewportModel(QtCore.QObject):
    changed = QtCore.pyqtSignal()

    def __init__(self, model):
        super(SubjectwiseViewportModel, self).__init__()
        self._objects_loader_backend = Backend.objects_loader_backend()
        self._init_model(model)
        self._init_3d_objects()

    def _init_model(self, model):
        self._analysis_model = model
        self._analysis_model.changed.connect(self.on_analysis_model_changed)
        self._analysis_model.input_files_changed.connect(\
                self.on_analysis_model_input_files_changed)
        self._analysis_model.output_files_changed.connect(\
                self.on_analysis_model_output_files_changed)

    def _init_3d_objects(self):
        raise Exception("SubjectwiseViewportModel is an abstract class")

    @QtCore.Slot()
    def on_analysis_model_changed(self):
        # XXX : may need a cache ?
        self._init_3d_objects()
        self.changed.emit()

    @QtCore.Slot(list)
    def on_analysis_model_input_files_changed(self, changed_inputs):
        self._on_analysis_model_files_changed(changed_inputs,
                self._analysis_model.filename_from_input_parameter)

    @QtCore.Slot(list)
    def on_analysis_model_output_files_changed(self, changed_outputs):
        self._on_analysis_model_files_changed(changed_outputs,
                self._analysis_model.filename_from_output_parameter)

    def _on_analysis_model_files_changed(self, changed_parameters,
                                                filename_from_parameter):
        for parameter in changed_parameters:
            if not parameter in self.observed_objects.keys():
                continue
            object = self.observed_objects[parameter]
            filename = filename_from_parameter(parameter)
            if object is not None:
                if os.path.exists(filename):
                    object = self._objects_loader_backend.reload_object_if_needed(object)
                else:
                    object = None
            else:
                try:
                    object = self._objects_loader_backend.load_object(filename)
                except Exception, e:
                    # XXX: should be propagated to the GUI ?
                    print "error: parameter '%s':" % parameter, \
                            "can't load '%s'" % filename, e 
                    continue
            self.observed_objects[parameter] = object
            signal = self.signal_map.get(parameter)
            if signal is not None:
                self.__getattribute__(signal).emit()
 

class IntraAnalysisSubjectwiseViewportModel(SubjectwiseViewportModel):
    changed = QtCore.pyqtSignal()
    raw_mri_changed = QtCore.pyqtSignal()
    corrected_mri_changed = QtCore.pyqtSignal()
    brain_mask_changed = QtCore.pyqtSignal()
    split_mask_changed = QtCore.pyqtSignal()
    signal_map = { \
        'mri' : 'raw_mri_changed',
        'mri_corrected' : 'corrected_mri_changed',
        'brain_mask' : 'brain_mask_changed',
        'split_mask' : 'split_mask_changed'
    }

    def __init__(self, model):
        super(IntraAnalysisSubjectwiseViewportModel, self).__init__(model)

    def _init_3d_objects(self):
        self.observed_objects = { \
            'mri' : None,
            'mri_corrected' : None,
            'brain_mask' : None,
            'split_mask' : None
        }


class IntraAnalysisSubjectwiseViewportView(QtGui.QWidget):
    uifile = os.path.join(ui_directory, 'viewport_widget.ui')
    main_frame_style_sheet = '''
        #viewport_frame { background-color: white }
        #view1_frame, #view2_frame, #view3_frame, #view4_frame {
            border: 3px solid black;
            border-radius: 20px;
            background: black;
        }
        #view1_label, #view2_label, #view3_label, #view4_label {
            color: white;
        }
    '''

    def __init__(self, parent=None):
        super(IntraAnalysisSubjectwiseViewportView, self).__init__(parent)
        self.ui = loadUi(self.uifile, parent)
        self._views = []
        self._display_lib = IntraAnalysisDisplayLibrary()
        self._viewport_model = None

        self._init_widget()

    def set_model(self, model):
        if self._viewport_model is not None:
            self._viewport_model.changed.disconnect(self.on_model_changed)
            self._viewport_model.raw_mri_changed.disconnect(\
                                    self.on_raw_mri_changed)
            self._viewport_model.corrected_mri_changed.disconnect(\
                                    self.on_corrected_mri_changed)
            self._viewport_model.brain_mask_changed.disconnect(\
                                    self.on_brain_mask_changed)
            self._viewport_model.split_mask_changed.disconnect(\
                                    self.on_split_mask_changed)
        self._viewport_model = model
        self._viewport_model.changed.connect(self.on_model_changed)
        self._viewport_model.raw_mri_changed.connect(self.on_raw_mri_changed)
        self._viewport_model.corrected_mri_changed.connect(self.on_corrected_mri_changed)
        self._viewport_model.brain_mask_changed.connect(self.on_brain_mask_changed)
        self._viewport_model.split_mask_changed.connect(self.on_split_mask_changed)

    def _init_widget(self):
        self.ui.setStyleSheet(self.main_frame_style_sheet)
        for view_hook in [self.ui.view1_hook, self.ui.view2_hook, 
                          self.ui.view3_hook, self.ui.view4_hook]:
            QtGui.QVBoxLayout(view_hook)
            view = self._display_lib._backend.create_axial_view(view_hook)
            self._views.append(view)
        self.view1, self.view2, self.view3, self.view4 = self._views
        self._display_lib.initialize_views(self._views)
        
    @QtCore.Slot()
    def on_model_changed(self):
        self._display_lib._backend.clear_windows(self._views)

    @QtCore.Slot()
    def on_raw_mri_changed(self):
        object = self._viewport_model.observed_objects['mri']
        if object is not None:
            self._display_lib._backend.add_objects_to_window(object, self.view1)
            self._display_lib._backend.center_window_on_object(self.view1, object)

    @QtCore.Slot()
    def on_corrected_mri_changed(self):
        object = self._viewport_model.observed_objects['mri_corrected']
        if object is not None:
            self._display_lib._backend.set_palette(object, "Rainbow2")
            self._display_lib._backend.add_objects_to_window(object, self.view2)

    @QtCore.Slot()
    def on_brain_mask_changed(self):
        object = self._viewport_model.observed_objects['brain_mask']
        if object is not None:
            self._display_lib._backend.set_palette(object, "GREEN-lfusion")
            self._display_lib._backend.add_objects_to_window(object, self.view3)

    @QtCore.Slot()
    def on_split_mask_changed(self):
        object = self._viewport_model.observed_objects['split_mask']
        if object is not None:
            self._display_lib._backend.set_palette(object, "RAINBOW")
            self._display_lib._backend.add_objects_to_window(object, self.view4)


class DisplayLibrary(object):
    
    def __init__(self, backend):
        self._backend = backend
        self._backend.initialize_display()


class IntraAnalysisDisplayLibrary(DisplayLibrary):

    def __init__(self, backend=Backend.display_backend()):
        super(IntraAnalysisDisplayLibrary, self).__init__(backend)

    def initialize_views(self, views):
        self._backend.set_bgcolor_views(views, [0., 0., 0., 1.])
     
