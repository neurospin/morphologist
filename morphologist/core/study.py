import os
import json

from morphologist.core.utils import OrderedDict
from morphologist.core.analysis import AnalysisFactory, Parameters, ImportationError
from morphologist.core.constants import ALL_SUBJECTS
from morphologist.core.subject import Subject


class Study(object):
    default_outputdir = os.path.join(os.path.expanduser("~"),
                                'morphologist/studies/study')
    
    def __init__(self, analysis_type, name="undefined study", 
                 outputdir=default_outputdir, backup_filename=None, 
                 parameter_template_name=None):
        self.analysis_type = analysis_type # string : name of the analysis class
        self.name = name
        self.outputdir = outputdir
        self.subjects = OrderedDict()
        if parameter_template_name is None:
            self.parameter_template = self.analysis_cls().create_default_parameter_template(self.outputdir)
        else:
            self.parameter_template = self.analysis_cls().create_parameter_template(parameter_template_name, 
                                                                                    self.outputdir)
        if backup_filename is None:
            backup_filename = self.default_backup_filename_from_outputdir(outputdir)
        self.backup_filename = backup_filename
        self.analyses = {}

    def analysis_cls(self):
        return AnalysisFactory.get_analysis_cls(self.analysis_type)
    
    def _create_analysis(self):
        return AnalysisFactory.create_analysis(self.analysis_type, self.parameter_template)
        
    @staticmethod
    def default_backup_filename_from_outputdir(outputdir):
        return os.path.join(outputdir, 'study.json')

    @staticmethod
    def default_outputdir_from_backup_filename(backup_filename):
        return os.path.dirname(backup_filename)

    @classmethod
    def from_file(cls, backup_filename):
        try:
            with open(backup_filename, "r") as fd:
                    serialized_study = json.load(fd)
        except Exception, e:
            raise StudySerializationError("%s" %(e))

        try:
            study = cls.unserialize(serialized_study)
            study.backup_filename = backup_filename
        except KeyError, e:
            raise StudySerializationError("The information does not "
                                          "match with a study.")
        return study

    @classmethod
    def unserialize(cls, serialized):
        study = cls(analysis_type=serialized['analysis_type'], 
                    name=serialized['name'],
                    outputdir=serialized['outputdir'])
        for subject_id, serialized_subject in serialized['subjects'].iteritems():
            subject = Subject.unserialize(serialized_subject)
            study.subjects[subject_id] = subject
        for subject_id, subject in study.subjects.iteritems():
            if subject_id not in serialized['inputs']:
                raise StudySerializationError("Cannot find input params"
                                         " for subject %s" % str(subject))
            if subject_id not in serialized['outputs']:
                raise StudySerializationError("Cannot find output params" 
                                         " for subject %s" % str(subject))
            serialized_inputs = serialized['inputs'][subject_id] 
            serialized_outputs = serialized['outputs'][subject_id]
            inputs = Parameters.unserialize(serialized_inputs) 
            outputs = Parameters.unserialize(serialized_outputs)
            analysis = study._create_analysis()
            analysis.inputs = inputs
            analysis.outputs = outputs
            study.analyses[subject_id] = analysis
        return study

    @classmethod
    def from_organized_directory(cls, analysis_type, organized_directory, parameter_template_name):
        new_study = cls(analysis_type, outputdir=organized_directory, parameter_template_name=parameter_template_name)
        parameter_template = new_study.parameter_template
        subjects = parameter_template.get_subjects(exact_match=True)
        for subject in subjects:
            new_study.add_subject(subject, import_data=False)
        return new_study
    
    def save_to_backup_file(self):
        serialized_study = self.serialize()
        try:
            with open(self.backup_filename, "w") as fd:
                json.dump(serialized_study, fd, indent=4, sort_keys=True)
        except Exception, e:
            raise StudySerializationError("%s" %(e))
  
    def serialize(self):
        serialized = {}
        serialized['analysis_type'] = self.analysis_type
        serialized['name'] = self.name
        serialized['outputdir'] = self.outputdir
        serialized['subjects'] = {}
        for subject_id, subject in self.subjects.iteritems():
            serialized['subjects'][subject_id] = subject.serialize()
        serialized['inputs'] = {}
        serialized['outputs'] = {}
        for subject_id, analysis in self.analyses.iteritems():
            serialized['inputs'][subject_id] = analysis.inputs.serialize()
            serialized['outputs'][subject_id] = analysis.outputs.serialize()
        return serialized 

    def add_subject(self, subject, import_data=True):
        subject_id = subject.id()
        if subject_id in self.subjects:
            raise SubjectExistsError(subject)
        self.subjects[subject_id] = subject
        self.analyses[subject_id] = self._create_analysis()
        self.analyses[subject_id].set_parameters(subject)
        if import_data:
            self._import_subject(subject_id, subject)
            
    def _import_subject(self, subject_id, subject):
        try:
            new_imgname = self.analyses[subject_id].import_data(subject)
        except ImportationError:
            del self.subjects[subject_id]
            del self.analyses[subject_id]
            raise ImportationError("Importation failed for the " +
                        "following subject: %s." % str(subject))
        else:
            subject.filename = new_imgname

    def remove_subject_and_files_from_id(self, subject_id):
        subject = self.subjects[subject_id]
        self.parameter_template.remove_dirs(subject)
        self.remove_subject_from_id(subject_id)

    def remove_subject_from_id(self, subject_id):
        del self.subjects[subject_id]
        del self.analyses[subject_id]

    def has_subjects(self):
        return len(self.subjects) != 0

    def has_some_results(self, subject_ids=ALL_SUBJECTS):
        if subject_ids == ALL_SUBJECTS:
            subject_ids = self.subjects
        for subject_id in subject_ids:
            analysis = self.analyses[subject_id]
            if analysis.has_some_results():
                return True
        return False

    def has_all_results(self, subject_ids=ALL_SUBJECTS):
        if subject_ids == ALL_SUBJECTS:
            subject_ids = self.subjects
        for subject_id in subject_ids:
            analysis = self.analyses[subject_id]
            if not analysis.has_all_results():
                return False
        return True

    def clear_results(self, subject_ids=ALL_SUBJECTS):
        if subject_ids == ALL_SUBJECTS:
            subject_ids = self.subjects
        for subject_id in subject_ids:
            analysis = self.analyses[subject_id]
            analysis.clear_results()

    def __repr__(self):
        s = 'name :' + str(self.name) + '\n'
        s += 'outputdir :' + str(self.outputdir) + '\n'
        s += 'subjects :' + repr(self.subjects) + '\n'
        return s


class StudySerializationError(Exception):
    pass

class SubjectExistsError(Exception):
    pass
