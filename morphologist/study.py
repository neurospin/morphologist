from collections import defaultdict
import os
import json

from morphologist.analysis import Analysis, InputParameters, OutputParameters
from morphologist.analysis import MockAnalysis
from morphologist.intra_analysis import IntraAnalysis
from morphologist.intra_analysis import IntraAnalysisInputParameters, IntraAnalysisOutputParameters


class Subject(object):

    def __init__(self, imgname, groupname=None):
        self.imgname = imgname
        self.groupname = groupname

    def __repr__(self):
        s = '\t<imgname: ' + str(self.imgname) + ',\n'
        s += '\tgroupname: ' + str(self.groupname) + ',\n'
        return s

    def serialize(self):
        serialized = {}
        serialized['imgname'] = self.imgname
        serialized['groupname'] = self.groupname
        return serialized

    @classmethod
    def unserialize(cls, serialized):
        subject = cls(imgname=serialized['imgname'], 
                      groupname=serialized['groupname'])
        return subject

    def __cmp__(self, other):
        if self.imgname == other.imgname and self.groupname == other.groupname:
            return 0
        return 1


class Study(object):
    default_outputdir = os.path.join(os.getcwd(), '.morphologist/studies/study')

    def __init__(self, name="undefined study", outputdir=default_outputdir):
        self.name = name
        self.outputdir = outputdir
        self.subjects = {}
        self.analysis = {}

    @classmethod
    def from_file(cls, file_path):
        try:
            f = open(file_path, "r")
            serialized_study = json.load(f)
            f.close
        except Exception, e:
            raise StudySerializationError("%s: %s" %(type(e), e))

        study = cls.unserialize(serialized_study)
        return study


    @classmethod
    def unserialize(cls, serialized):
        study = cls(name=serialized['name'],
                    outputdir=serialized['outputdir'])
        for subject_name, serialized_subject in serialized['subjects'].iteritems():
            study.subjects[subject_name] = Subject.unserialize(serialized_subject)
        for subject_name in study.subjects.iterkeys():
            if subject_name not in serialized['input_params']:
                raise StudySerializationError("Cannot find input params"
                                         " for subject %s" %subjectname)
            if subject_name not in serialized['output_params']:
                raise StudySerializationError("Cannot find output params" 
                                         " for subject %s" %subjectname)
            serialized_input_params = serialized['input_params'][subject_name] 
            serialized_output_params = serialized['output_params'][subject_name]
            input_params = InputParameters.unserialize(serialized_input_params) 
            output_params = OutputParameters.unserialize(serialized_output_params)
            analysis = study._create_analysis()
            analysis.input_params = input_params
            analysis.output_params = output_params
            # TO DO => check if the parameters are compatibles with the analysis ?
            study.analysis[subject_name] = analysis
        return study

    def save_to_file(self, filename):
        try:
            f = open(filename, "w")
            serialized_study = self.serialize()
            json.dump(serialized_study, f, indent=4, sort_keys=True)
            f.close()
        except Exception, e:
            raise StudySerializationError("%s: %s" %(type(e), e))
  


    def serialize(self):
        serialized = {}
        serialized['name'] = self.name
        serialized['outputdir'] = self.outputdir
        serialized['subjects'] = {}
        for subjectname, subject in self.subjects.iteritems():
            serialized['subjects'][subjectname] = subject.serialize()
        serialized['input_params'] = {}
        serialized['output_params'] = {}
        for subjectname, analysis in self.analysis.iteritems():
            serialized['input_params'][subjectname] = analysis.input_params.serialize()
            serialized['output_params'][subjectname] = analysis.output_params.serialize()
        return serialized 


    def __cmp__(self, other):
        if self.name != other.name or self.outputdir != other.outputdir:
            return 1
        if self.subjects != other.subjects:
            return 1
        for subject in self.subjects:
            if self.analysis[subject].input_params != other.analysis[subject].input_params:
                return 1
            if self.analysis[subject].output_params != other.analysis[subject].output_params:
                return 1
        return 0
         

    @staticmethod
    def define_subjectname_from_filename(filename):
        return os.path.splitext(os.path.basename(filename))[0]

    def add_subject_from_file(self, filename, subjectname=None, groupname=None):
        if subjectname is None:
            subjectname = self.define_subjectname_from_filename(subjectname)
        if subjectname in self.subjects:
            raise SubjectNameExistsError("subjectname")
        subject = Subject(filename, groupname)
        self.subjects[subjectname] = subject
        self.analysis[subjectname] = self._create_analysis()


    def _create_analysis(self):
        return IntraAnalysis() 


    def set_analysis_parameters(self, parameter_template):
        for subjectname, subject in self.subjects.iteritems():
            self.analysis[subjectname].set_parameters(parameter_template, 
                                                      subjectname,
                                                      subject.imgname,
                                                      self.outputdir)
        
    def list_subject_names(self):
        return self.subjects.keys()

    def run_analyses(self):
        for analysis in self.analysis.itervalues():
            analysis.run()     

    def wait_analyses_end(self):
        for analysis in self.analysis.itervalues():
            analysis.wait()

    def stop_analyses(self):
        for analysis in self.analysis.itervalues():
            analysis.stop()

    def analyses_ended_with_success(self):
        success = True
        for analysis in self.analysis.itervalues():
            if analysis.last_run_failed():
                success = False
                break
        return success

    def clear_results(self):
        for analysis in self.analysis.itervalues():
            analysis.clear_output_files()

    def __repr__(self):
        s = 'name :' + str(self.name) + '\n'
        s += 'outputdir :' + str(self.outputdir) + '\n'
        s += 'subjects :' + repr(self.subjects) + '\n'
        return s


class MockStudy(Study):

    def _create_analysis(self):
        return MockAnalysis()

class StudySerializationError(Exception):
    pass

class SubjectNameExistsError(Exception):
    pass

def create_input_parameters(subject_name, img_file_path, output_dir):
    input_params = IntraAnalysisInputParameters.from_brainvisa_hierarchy(img_file_path)
    return input_params


def create_output_parameters(subject_name, img_file_path, output_dir):
    output_params = IntraAnalysisOutputParameters.from_brainvisa_hierarchy(output_dir, 
                                                                           subject_name)
    return output_params


def create_analysis():
    intra_analysis = IntraAnalysis()    
    return intra_analysis


