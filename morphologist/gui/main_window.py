import os

from morphologist.backends import Backend
from .qt_backend import QtCore, QtGui, loadUi 
from .gui import ui_directory 
from morphologist.study import Study
from morphologist.study import StudySerializationError
from .manage_study import ManageStudyWindow
from morphologist.analysis import MissingParameterValueError
from morphologist.intra_analysis import IntraAnalysis
from morphologist.runner import OutputFileExistError, MissingInputFileError, SWRunner#, ThreadRunner


objects_kept_alive = []

def keep_objects_alive(objects):
    global objects_kept_alive
    objects_kept_alive += objects


class LazyStudyModel(QtCore.QObject):
    changed = QtCore.pyqtSignal()
    status_changed = QtCore.pyqtSignal()


    def __init__(self, study=None, runner=None, parent=None):
        super(LazyStudyModel, self).__init__(parent)
        self._study = None
        self._runner = None
        self._subjectnames = []
        self._status = {}

        self._update_interval = 2 # in seconds
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(self._update_interval * 1000)
        self._timer.timeout.connect(self._update_all_status)
        if study is not None and runner is not None:
            self.set_study(study, runner)
        self._timer.start()


    def set_study(self, study, runner):
        self._study = study
        self._runner = runner
        self._subjectnames = self._study.subjects.keys()
        self._subjectnames.sort()
        self._status = {}
        self._update_all_status()
        self.changed.emit()

    def get_status(self, index):
        subjectname = self._subjectnames[index]
        return self._status[subjectname]

    def get_subjectname(self, index):
        return self._subjectnames[index]

    def subject_count(self):
        return len(self._subjectnames)

    @QtCore.Slot()
    def _update_all_status(self):
        has_changed = False
        for subjectname in self._subjectnames:
            has_changed |= self._update_status_for_one_subject(subjectname) 
        if has_changed:
            self.status_changed.emit()

    def _update_status_for_one_subject(self, subjectname):
        analysis = self._study.analyses[subjectname]
        has_changed = False
        if self._runner.is_running():
            has_changed = self._update_one_status_for_one_subject_if_needed(\
                                                subjectname, "is running")
        elif self._runner.last_run_failed():
            has_changed = self._update_one_status_for_one_subject_if_needed(\
                                                subjectname, "last run failed")
        elif len(analysis.output_params.list_existing_files()) == 0:
            has_changed = self._update_one_status_for_one_subject_if_needed(\
                                                subjectname, "no output files")
        elif len(analysis.output_params.list_missing_files()) == 0:
            has_changed = self._update_one_status_for_one_subject_if_needed(\
                                            subjectname, "output files exist")
        else:
            has_changed = self._update_one_status_for_one_subject_if_needed(\
                                        subjectname, "some output files exist")
        return has_changed

    def _update_one_status_for_one_subject_if_needed(self, subjectname, status):
        has_changed = False 
        if self._status.get(subjectname) != status:
            self._status[subjectname] = status
            has_changed = True
        return has_changed


class StudyTableModel(QtCore.QAbstractTableModel):
    SUBJECTNAME_COL = 0 
    SUBJECTSTATUS_COL = 1
    header = ['name', 'status'] #TODO: to be extended

    def __init__(self, study_model=None, parent=None):
        super(StudyTableModel, self).__init__(parent)
        self._study_model = None
        self._subjectnames = None
        if study_model is not None:
            self.setModel(study_model)

    def setModel(self, study_model):
        self.beginResetModel()
        if self._study_model is not None:
            self._study_model.status_changed.disconnect(\
                        self.on_study_model_status_changed)
            self._study_model.changed.disconnect(self.on_study_model_changed)
        self._study_model = study_model
        self._study_model.status_changed.connect(\
                    self.on_study_model_status_changed)
        self._study_model.changed.connect(self.on_study_model_changed)
        self.endResetModel()
        self.reset()

    def subjectname_from_row_index(self, index):
        return self._study_model.get_subjectname(index)

    def rowCount(self, parent=QtCore.QModelIndex()):
        return self._study_model.subject_count()

    def columnCount(self, parent=QtCore.QModelIndex()):
        return 2 #TODO: to be extended

    def headerData(self, section, orientation, role=QtCore.Qt.DisplayRole):
        if role == QtCore.Qt.DisplayRole:
            if orientation == QtCore.Qt.Vertical:
                return
            elif orientation == QtCore.Qt.Horizontal:
                return self.header[section]

    def data(self, index, role=QtCore.Qt.DisplayRole):
        row, column = index.row(), index.column()
        if role == QtCore.Qt.DisplayRole:
            if column == StudyTableModel.SUBJECTNAME_COL:
                return self._study_model.get_subjectname(row)
            if column == StudyTableModel.SUBJECTSTATUS_COL:
                return self._study_model.get_status(row)

    @QtCore.Slot()                
    def on_study_model_status_changed(self):
        self._update_all_index()

    def _update_all_index(self):
        top_left = self.index(0, StudyTableModel.SUBJECTSTATUS_COL,
                              QtCore.QModelIndex())
        bottom_right = self.index(self.rowCount(),
                                  StudyTableModel.SUBJECTSTATUS_COL, 
                                  QtCore.QModelIndex())
        self.dataChanged.emit(top_left, bottom_right)

    @QtCore.Slot()                
    def on_study_model_changed(self):
        self.reset()


class StudyTableView(QtGui.QWidget):
    uifile = os.path.join(ui_directory, 'display_study.ui')
    # FIXME : missing handling of sorting triangle icon
    header_style_sheet = '''
        QHeaderView::section {
            background-color: qlineargradient( x1:0 y1:0, x2:0 y2:1,
                                               stop:0 gray, stop:1 black);
            color:white;
            border: 0px
        }'''
    subjectname_column_width = 100    

    def __init__(self, parent=None):
        super(StudyTableView, self).__init__(parent)
        self.ui = loadUi(self.uifile, self)
        self._tableview = self.ui.subjects_tableview
        self._tablemodel = None
        self._init_widget()

    def _init_widget(self):
        header = self._tableview.horizontalHeader()
        # FIXME : stylesheet has been disable and should stay disable until
        # subject list sorting has not been implementing
        #header.setStyleSheet(self.header_style_sheet)
        header.resizeSection(0, self.subjectname_column_width)

    @QtCore.Slot()
    def on_modelReset(self):
        self._tableview.selectRow(0)

    def setModel(self, model):
        if self._tablemodel is not None:
            self._tablemodel.modelReset.disconnect(self.on_modelReset)
        self._tablemodel = model
        self._tableview.setModel(model)
        self._tablemodel.modelReset.connect(self.on_modelReset)
        self.on_modelReset()

    def setSelectionModel(self, selection_model):
        self._tableview.setSelectionModel(selection_model)


class SubjectwiseViewportModel(QtCore.QObject):
    changed = QtCore.pyqtSignal()

    def __init__(self):
        super(SubjectwiseViewportModel, self).__init__()
        self._analysis_model = None

    def setModel(self, model):
        if self._analysis_model is not None:
            self._analysis_model.changed.disconnect(\
                        self.on_analysis_model_changed)
            self._analysis_model.outputs_changed.disconnect(\
                        self.on_analysis_model_outputs_changed)
        self._analysis_model = model
        self._analysis_model.changed.connect(self.on_analysis_model_changed)
        self._analysis_model.outputs_changed.connect(\
                self.on_analysis_model_outputs_changed)
        self.changed.emit()

    @QtCore.Slot()
    def on_analysis_model_changed(self):
        print "on_analysis_model_changed"

    @QtCore.Slot()
    def on_analysis_model_outputs_changed(self):
        print "on_analysis_model_outputs_changed"


class IntraAnalysisSubjectwiseViewportModel(SubjectwiseViewportModel):

    def __init__(self):
        super(IntraAnalysisSubjectwiseViewportModel, self).__init__()
        
    def getRawMRI(self):
        pass #TODO


class IntraAnalysisSubjectwiseViewportView(QtGui.QWidget):
    uifile = os.path.join(ui_directory, 'viewport.ui')
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
        self._view_hooks = [self.ui.view1_hook, self.ui.view2_hook, 
                            self.ui.view3_hook, self.ui.view4_hook]
        self._display_lib = IntraAnalysisDisplayLibrary()
        self._model = None

        self._init_widget()

    def setModel(self, model):
        if self._model is not None:
            self._model.changed.disconnect(self.on_model_changed)
        self._model = model
        self._model.changed.connect(self.on_model_changed)

    def _init_widget(self):
        self.ui.setStyleSheet(self.main_frame_style_sheet)
        for view_hook in self._view_hooks:
            layout = QtGui.QVBoxLayout(view_hook)
        self._create_intra_analysis_views()

    def _create_intra_analysis_views(self):
        w1 = self._display_lib.create_normalized_raw_T1_with_ACPC_view(self.ui.view1_hook)
        w2 = self._display_lib.create_bias_corrected_T1_view(self.ui.view2_hook)
        w3 = self._display_lib.create_brain_mask_view(self.ui.view3_hook)
        w4 = self._display_lib.create_split_brain_view(self.ui.view4_hook)
        keep_objects_alive([w1, w2, w3, w4])
        self._display_lib.initialize_views([w1, w2, w3, w4])
        
    @QtCore.Slot()
    def on_model_changed(self):
        print "on_model_changed"
        # FIXME: move this lines
        return
        t1mri = anatomist_instance.loadObject("/volatile/perrot/data/icbm/icbm/icbm100T/t1mri/default_acquisition/icbm100T.ima")
        awindows.append(t1mri)
        awindow.addObjects(t1mri)


class DisplayLibrary(object):
    
    def __init__(self, backend):
        self._backend = backend
        self._backend.initialize_display()


class IntraAnalysisDisplayLibrary(DisplayLibrary):

    def __init__(self, backend=Backend.display_backend()):
        super(IntraAnalysisDisplayLibrary, self).__init__(backend)

    def create_normalized_raw_T1_with_ACPC_view(self, parent=None):
        return self._backend.create_axial_view(parent)

    def create_bias_corrected_T1_view(self, parent=None):
        return self._backend.create_axial_view(parent)

    def create_brain_mask_view(self, parent=None):
        return self._backend.create_axial_view(parent)

    def create_split_brain_view(self, parent=None):
        return self._backend.create_axial_view(parent)

    def initialize_views(self, views):
        self._backend.set_bgcolor_views(views, [0., 0., 0., 1.])


class IntraAnalysisWindow(object):
    uifile = os.path.join(ui_directory, 'intra_analysis.ui')

    def __init__(self, study_file=None):
        self.ui = loadUi(self.uifile)

        self.study = None
        self.runner = None
        self.study_model = LazyStudyModel()
        
        self.study_tablemodel = StudyTableModel(self.study_model)
        self.study_selection_model = QtGui.QItemSelectionModel(\
                                            self.study_tablemodel)
        self.viewport_model = IntraAnalysisSubjectwiseViewportModel()

        self.study_view = StudyTableView(self.ui.study_widget_dock)
        self.study_view.setModel(self.study_tablemodel)
        self.study_view.setSelectionModel(self.study_selection_model)
        self.ui.study_widget_dock.setWidget(self.study_view)

        self.viewport_view = IntraAnalysisSubjectwiseViewportView(\
                                        self.ui.viewport_frame)
        self.viewport_view.setModel(self.viewport_model)

        self.manage_study_window = None

        self._init_qt_connections()
        self._init_widget()

        self.set_study(self._create_study(study_file))

    def _init_qt_connections(self):
        self.ui.run_button.clicked.connect(self.on_run_button_clicked)
        self.ui.stop_button.clicked.connect(self.on_stop_button_clicked)
        self.ui.action_new_study.triggered.connect(self.on_new_study_action)
        self.ui.action_open_study.triggered.connect(self.on_open_study_action)
        self.ui.action_save_study.triggered.connect(self.on_save_study_action)
        self.study_selection_model.currentChanged.connect(self.on_selection_changed)

    def _init_widget(self):
        pass

    def _create_study(self, study_file=None):
        if study_file:
            study = Study.from_file(study_file)
            return study
        else:
            return Study()
        
    def _create_runner(self, study):
        #return ThreadRunner(study)
        return SWRunner(study)

    def _run_analyses(self):
        run = False
        try:
            self.runner.run()
            run = True
        except MissingParameterValueError, e:
            QtGui.QMessageBox.critical(self.ui, 
                                       "Run analysis error", 
                                       "Some parameter value are missing.\n%s" %(e))
        except MissingInputFileError, e:
            QtGui.QMessageBox.critical(self.ui, 
                                       "Run analysis error", 
                                       "Some input files do not exist.\n%s" %(e))
        except OutputFileExistError, e:
            answer = QtGui.QMessageBox.question(self.ui, "Existing results",
                                                "Some results already exist.\n" 
                                                "Do you want to delete them ?", 
                                                QtGui.QMessageBox.Yes, QtGui.QMessageBox.No)
            if answer == QtGui.QMessageBox.Yes:
                self.study.clear_results()
                run = self._run_analyses()
        return run

        
    @QtCore.Slot()
    def on_run_button_clicked(self):
        self.ui.run_button.setEnabled(False)
        if self._run_analyses():
            self.ui.stop_button.setEnabled(True)
        else:
            self.ui.run_button.setEnabled(True)

    @QtCore.Slot()
    def on_stop_button_clicked(self):
        self.ui.stop_button.setEnabled(False)
        self.runner.stop()
        self.ui.run_button.setEnabled(True)

    @QtCore.Slot()
    def on_new_study_action(self):
        study = self._create_study()
        self.manage_study_window = ManageStudyWindow(study, self.ui)
        self.manage_study_window.ui.accepted.connect(self.on_study_dialog_accepted)
        self.manage_study_window.ui.show()
        
    @QtCore.Slot()
    def on_study_dialog_accepted(self):
        QtGui.QApplication.setOverrideCursor(QtGui.QCursor(QtCore.Qt.WaitCursor))
        study = self.manage_study_window.study
        study.import_data(IntraAnalysis.BRAINVISA_PARAM_TEMPLATE)
        study.set_analysis_parameters(IntraAnalysis.BRAINVISA_PARAM_TEMPLATE)
        self.set_study(study)
        self.manage_study_window = None
        QtGui.QApplication.restoreOverrideCursor()
        msg = "The images have been copied in %s directory." % study.outputdir
        msgbox = QtGui.QMessageBox(QtGui.QMessageBox.Information,
                                   "Images importation", msg,
                                   QtGui.QMessageBox.Ok, self.ui)
        msgbox.show()

    @QtCore.Slot()
    def on_open_study_action(self):
        filename = QtGui.QFileDialog.getOpenFileName(self.ui, caption = "Open a study", directory="", 
                                                     options=QtGui.QFileDialog.DontUseNativeDialog)
        if filename:
            try:
                study = self._create_study(filename)
            except StudySerializationError, e:
                QtGui.QMessageBox.critical(self.ui, 
                                          "Cannot load the study", "%s" %(e))
            else:
                self.set_study(study) 

    @QtCore.Slot()
    def on_save_study_action(self):
        filename = QtGui.QFileDialog.getSaveFileName(self.ui, caption="Save a study", directory="", 
                                                     options=QtGui.QFileDialog.DontUseNativeDialog)
        if filename:
            try:
                self.study.save_to_file(filename)
            except StudySerializationError, e:
                QtGui.QMessageBox.critical(self.ui, 
                                          "Cannot save the study", "%s" %(e))

    # FIXME : move code elsewhere
    @QtCore.Slot("QModelIndex &, QModelIndex &")
    def on_selection_changed(self, current, previous):
        subjectname = self.study_tablemodel.subjectname_from_row_index(current.row())
        analysis = self.study.analyses[subjectname]
        # FIXME : to be removed
        #self.viewport_model.set_current_subjectname(subjectname)

    def set_study(self, study):
        self.study = study
        self.runner = self._create_runner(self.study)
        self.study_model.set_study(self.study, self.runner)
        self.ui.setWindowTitle("Morphologist - %s" % self.study.name)


def create_main_window(study_file=None, mock=False):
    if study_file: print "load " + str(study_file)
    if not mock:
        return IntraAnalysisWindow(study_file)
    else:
        print "mock mode"
        from morphologist.tests.mocks.main_window import MockIntraAnalysisWindow
        return MockIntraAnalysisWindow(study_file) 
