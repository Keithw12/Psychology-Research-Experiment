# -*- coding: utf-8 -*-
"""
Created on Wed Nov 20 11:56:13 2019

@author: Keith Wilcox
@Version:  4.1 (Fixed previously unknown state bug by adding transition 10)
@Version:  5.0 (Removed visicon usage to determine stimulus visibility.  Using event's instead)
"""

import actr
import pandas
import time
import logging
import re
import os

#Recommend disabling Model trace with setting :v to nil in the model file for debugging purposes

debug = 1

logging.basicConfig()
logger = logging.getLogger()

logger.setLevel(logging.WARNING)
# logger.setLevel(logging.INFO)

#STATES
#STATE 0 - Show initial block stimuli
#STATE 2 - Show fixation cross, Display Stimuli
#STATE 3 - 1 or 0 displayed, Fixation Cross, Stimulus
#STATE 4 - Too SLow displayed, fixation cross, stimulus
# REMOVED(v4) - STATE 5 - Too slow displayed, next initial stimuli shown
# REMOVED(v4) - STATE 6 - 1 or 0 displayed, next initial stimuli shown
#STATE 7 - Experiment complete
#STATE 8 - Feedback displayed, Schedule "done"
#STATE 9 - Done displayed, wait for spacebar input

# actr.load_act_r_model(os.path.abspath("rlwm_model_nomeaning.lisp").replace('/', ';')[1:])
# actr.load_act_r_model(os.path.abspath("rlwm_model.lisp"))  # <--I have to use this one, previous line errors for me.(windows related?)

class RLWM:
    def __init__(self, maincsv_df, subject_num, condition):
        #open block_df.csv to get list of csv's in stim_path column.  (May not need ns/name columns)
        self.maincsv_df = pandas.read_csv(maincsv_df,header=0,usecols=["name","stim_path","ns"])
        #number of rows/csv files to parse
        self.index_size = len(self.maincsv_df.index)
        #Dictionary to store each sequence csv as a dataframe object
        self.sequences_csv_dfs = {}
        #store set size integer for each block
        self.set_sizes = [self.maincsv_df["ns"].iloc[i] for i in range(self.index_size)]
        #store stimulus sequence and answers
        self.initial_set_stimuli = []
        self.corr_ans_lists = []
        self.current_state = 0
        #preset coord's for displaying initial stimuli
        self.my_y = [100,100,100,200,200,200]
        self.my_x = [0,100,200,0,100,200]
        self.sequence_num = 0
        self.current_block = 0
        self.visicon_output = None
        #used for time start and end for script logging
        self.start = None
        self.end = None
        self.stim_substring = None
        self.window = None
        self.textIdDict = {
                "text_id": None
                }
        self.event_id_dict = {
                "next_stimulus": None,
                "too_slow": None,
                "fixation_cross": None,
                "initial_stimuli": None,
                "done": None
                }
        self.is_stim_vis = False
        self.initial_time = 0
        self.final_time = 0
        self.subject_num = subject_num
        self.condition = condition
        self.data = {
            "stimulus": [], # image/text shown
            "response": [], # key that was pressed, string NA if no response
            # we only care about responses to single images and not begin/end block
            "corr_response": [], # key that was correct
            "accuracy": [], # response == corr_response
            "rt": [], # response time (button_press_time - stim_start_time) or string NA if no response
            "block_num": [], # block number
            "set_size": []
        }
        # can write data with just
        # out_data = pandas.DataFrame.from_dict(self.data)
        # out_data['subject_num'] = self.subject_num
        # out_data['condition'] = self.condition
        # out_data.to_csv('RLWM_{}_{}.csv'.format(self.subject_num, self.condition))

    def curr_time(self):
        return  (time.monotonic()-self.start)

    def add_data(self,condition,key="NA"):
        self.data['set_size'].append(self.set_sizes[self.current_block])
        self.data["stimulus"].append(self.initial_set_stimuli[self.current_block][self.sequence_num-1][:])
        self.data["corr_response"].append(self.corr_ans_lists[self.current_block][self.sequence_num-1][:])
        self.data["block_num"].append(self.current_block + 1)
        if condition == "too_slow":
            self.data["response"].append("NA")
            self.data["accuracy"].append(int(0))  #<--- NA for Too Slow?
            self.data["rt"].append("NA")
        elif condition == "input_given":
            self.data["response"].append(key)
            self.data["accuracy"].append(int(key == self.corr_ans_lists[self.current_block][self.sequence_num-1][:]))
            self.data["rt"].append(actr.mp_time_ms() - self.initial_time)

    def post_event_hook(self, event_id):
        t1 = self
        if event_id == t1.event_id_dict["next_stimulus"]:
            t1.is_stim_vis = True
            logger.info("%s:state %s, post_event_hook():t1.event_id_dict[\"next_stimulus\"] triggered, event_id=%s" % ("{0:.2f}".format(t1.curr_time()),t1.current_state,event_id))
            #print("actr.mp_time_ms()=",actr.mp_time_ms())
            #actr.print_visicon()
            t1.initial_time = actr.mp_time_ms()
        elif event_id == t1.event_id_dict["too_slow"]:
            t1.is_stim_vis = False
            self.add_data("too_slow")
            logger.info("%s:state %s, Too Slow Event.  t1.sequence_num=%s" % ("{0:.2f}".format(self.curr_time()),t1.current_state,t1.sequence_num))
            #transition 2
            if t1.current_state == 2:
                t1.current_state = 4
                t1.schedule_fixation_cross(.5)
                t1.schedule_next_stimulus(1)
                t1.schedule_too_slow(2.5)
                logger.info("%s:state %s, Transition 2" % ("{0:.2f}".format(self.curr_time()),t1.current_state))
            #transition 4
            elif t1.current_state == 3 and not t1.block_finished():
                t1.current_state = 4
                logger.info("%s:state %s, Transition 4" % ("{0:.2f}".format(self.curr_time()),t1.current_state))
                t1.schedule_fixation_cross(.5)
                t1.schedule_next_stimulus(1)
                t1.schedule_too_slow(2.5)
            #transition 5
            elif t1.current_state == 3 and t1.block_finished() and not t1.all_blocks_finished():
                t1.current_state = 8
                logger.info("%s:state %s, Transition 5" % ("{0:.2f}".format(self.curr_time()),t1.current_state))
                t1.current_block += 1
                t1.schedule_text("done",.5)
            #transition 7
            elif t1.current_state == 4 and not t1.block_finished():
                #don't change state
                logger.info("%s:state %s, Transition 7" % ("{0:.2f}".format(self.curr_time()),t1.current_state))
                t1.schedule_fixation_cross(.5)
                t1.schedule_next_stimulus(1)
                t1.schedule_too_slow(2.5)
            #transition 11
            elif t1.current_state == 3 and t1.block_finished() and t1.all_blocks_finished():
                t1.current_state = 7
                logger.info("%s:state %s, Transition 11" % ("{0:.2f}".format(self.curr_time()),t1.current_state))
                t1.schedule_text("ExperimentComplete",.5)
            #transition 13
            elif t1.current_state == 4 and t1.block_finished() and t1.all_blocks_finished():
                t1.current_state = 7
                logger.info("%s:state %s, Transition 13" % ("{0:.2f}".format(self.curr_time()),t1.current_state))
                t1.schedule_text("ExperimentComplete",.5)
            #transition 15
            elif t1.current_state == 4 and t1.block_finished() and not t1.all_blocks_finished():
                t1.current_state = 8
                logger.info("%s:state %s, Transition 15" % ("{0:.2f}".format(self.curr_time()),t1.current_state))
                t1.current_block += 1
                t1.schedule_text("done",.5)
        elif event_id == t1.event_id_dict["done"]:
            if t1.current_state == 8:
                t1.current_state = 9
                logger.info("%s:state %s, Transition 16" % ("{0:.2f}".format(self.curr_time()),t1.current_state))


    def respond_to_key_press(self, model, key):
        t1 = self

        #print("respond_to_key_press->actr.mp_time_ms()=",actr.mp_time_ms())
        #actr.print_visicon()
        #transition 0
        if t1.current_state == 0 and key == "space":
            t1.current_state = 2
            t1.clear_screen()
            # print("clear_screen()")
            t1.display_fixation()
            # print("t1.display_fixation()")
            t1.schedule_next_stimulus(0.5)
            # print("t1.schedule_next_stimulus(0.5)")
            t1.schedule_too_slow(2)
            logger.info("%s:state %s, Transition 0" % ("{0:.2f}".format(self.curr_time()),t1.current_state))
        #transition 1
        elif t1.current_state == 2 and t1.stimulus_visible():
            t1.current_state = 3
            t1.delete_event(t1.event_id_dict["too_slow"])
            t1.display_feedback(key)
            t1.schedule_fixation_cross(0.5)
            t1.schedule_next_stimulus(1)
            t1.schedule_too_slow(2.5)
            logger.info("%s:state %s, Transition 1" % ("{0:.2f}".format(self.curr_time()),t1.current_state))
        #transition 3
        elif t1.current_state == 3 and t1.stimulus_visible() and not t1.block_finished():
            #don't change state
            t1.delete_event(t1.event_id_dict["too_slow"])
            t1.display_feedback(key)
            t1.schedule_fixation_cross(0.5)
            t1.schedule_next_stimulus(1)
            t1.schedule_too_slow(2.5)
            logger.info("%s:state %s, Transition 3" % ("{0:.2f}".format(self.curr_time()),t1.current_state))
        #transition 6
        elif t1.current_state == 3 and t1.stimulus_visible() and t1.block_finished() and not t1.all_blocks_finished():
            t1.current_state = 8
            logger.info("%s:state %s, Transition 6" % ("{0:.2f}".format(self.curr_time()),t1.current_state))
            t1.delete_event(t1.event_id_dict["too_slow"])
            t1.display_feedback(key)
            t1.current_block += 1
            t1.schedule_text("done",0.5)
            logger.info("%s:state %s, Transition 6" % ("{0:.2f}".format(self.curr_time()),t1.current_state))
        #transition 8
        elif t1.current_state == 4 and t1.stimulus_visible() and t1.block_finished() and not t1.all_blocks_finished():
            t1.current_state = 8
            t1.delete_event(t1.event_id_dict["too_slow"])
            t1.display_feedback(key)
            t1.current_block += 1
            t1.schedule_text("done",0.5)
            logger.info("%s:state %s, Transition 8" % ("{0:.2f}".format(self.curr_time()),t1.current_state))
        #transition 9
        elif t1.current_state == 9 and key == "space":
            t1.clear_screen()
            t1.schedule_initial_stimuli(t1.set_sizes[t1.current_block],True)    #<-- when True, it displays immediately
            t1.current_state = 0
            t1.sequence_num = 0
            logger.info("%s:state %s, Transition 9" % ("{0:.2f}".format(self.curr_time()),t1.current_state))
        #transition 10
        elif t1.current_state == 4 and t1.stimulus_visible() and not t1.block_finished():
            t1.current_state = 3
            t1.delete_event(t1.event_id_dict["too_slow"])
            t1.display_feedback(key)
            t1.schedule_fixation_cross(0.5)
            t1.schedule_next_stimulus(1)
            t1.schedule_too_slow(2.5)
            logger.info("%s:state %s, Transition 10" % ("{0:.2f}".format(self.curr_time()),t1.current_state))
        #transition 12
        elif t1.current_state == 3 and t1.block_finished() and t1.all_blocks_finished() and t1.stimulus_visible():
            t1.current_state = 7
            t1.delete_event(t1.event_id_dict["too_slow"])
            t1.display_feedback(key)
            t1.schedule_text("ExperimentComplete",0.5)
            logger.info("%s:state %s, Transition 12" % ("{0:.2f}".format(self.curr_time()),t1.current_state))
        #transition 14
        elif t1.current_state == 4 and t1.stimulus_visible() and t1.block_finished() and t1.all_blocks_finished():
            t1.current_state = 7
            t1.delete_event(t1.event_id_dict["too_slow"])
            t1.display_feedback(key)
            t1.schedule_text("ExperimentComplete",0.5)
            logger.info("%s:state %s, Transition 14" % ("{0:.2f}".format(self.curr_time()),t1.current_state))
        #Catch all for error debugging
        #else:
        #    logger.info("%s:state %s, No Matching Transitions!\nInputs:\nt1.stimulus_visible()=%s\nt1.block_finished()=%s\nt1.all_blocks_finished()=%s\nt1.visicon_output=%s\nself.textIdDict[\"text_id\"]=%s"
        #                % ("{0:.2f}".format(curr_time()),t1.current_state,t1.stimulus_visible(),t1.block_finished(),t1.all_blocks_finished(),t1.visicon_output,t1.textIdDict["text_id"]))


    def unpack_data(self):
        for i in range(self.index_size):
            self.sequences_csv_dfs[i] = pandas.read_csv("data/{}/{}".format(self.subject_num, self.maincsv_df["stim_path"].iloc[i]))
            self.initial_set_stimuli.append(self.sequences_csv_dfs[i]["stimFile"].iloc[0:])
            self.corr_ans_lists.append(self.sequences_csv_dfs[i]["corr_ans"].iloc[0:])
            #format the strings:  "stim/images6_animal/animal1.bmp" with "animal1" for example
            for j in range(len(self.initial_set_stimuli[i].index)):
                match = re.search('/(.+?)mp', self.initial_set_stimuli[i][j])
                match = re.search('/(.+?).b', match.group(1))
                self.initial_set_stimuli[i][j] = match.group(1)

    #unused, for debugging purposes
    def output_data(self):
        for i in range(self.index_size):
            print(self.initial_set_stimuli[i])

    def experiment_initialization(self, vis=False):
        actr.reload()
        actr.add_command("unit2-key-press", self.respond_to_key_press,
                         "Assignment 2 task output-key monitor")
        actr.add_command("my-event-hook", self.post_event_hook,
                         "called after an event")
        actr.monitor_command("output-key","unit2-key-press")
        actr.call_command("add-post-event-hook","my-event-hook")
        self.window = actr.open_exp_window("Leter difference task", visible=vis)
        self.unpack_data()

    def delete_event(self,eventid,event_name="too_slow"):
        actr.delete_event(eventid)

    def block_finished(self):
        return (self.sequence_num == len(self.initial_set_stimuli[self.current_block].index))

    def all_blocks_finished(self):
        return ((self.current_block) == (self.index_size-1))

    def stimulus_visible(self):
        return self.is_stim_vis

    def display_fixation(self):
        self.textIdDict["text_id"] = actr.add_text_to_exp_window(self.window,"+",x=150,y=150)
        self.block_next_stim_event = True

    def display_feedback(self, key):
        self.is_stim_vis = False
        self.add_data("input_given",key)
        if (key == self.corr_ans_lists[self.current_block][self.sequence_num-1][:]):
            actr.modify_text_for_exp_window(self.textIdDict["text_id"],text="1",x=150,y=150)
        else:
            actr.modify_text_for_exp_window(self.textIdDict["text_id"],text="0",x=150,y=150)

    def clear_screen(self):
        actr.clear_exp_window(self.window)

    def schedule_initial_stimuli(self,stim_size,initial=False,time=0):
        if initial == True:
            if stim_size == 3:
                for row in range(3):
                    actr.add_text_to_exp_window(self.window, self.initial_set_stimuli[self.current_block][row][:], x=self.my_x[row], y=self.my_y[row])
            else:
                for row in range(6):
                    actr.add_text_to_exp_window(self.window, self.initial_set_stimuli[self.current_block][row][:], x=self.my_x[row], y=self.my_y[row])
        else:
            if stim_size == 3:
                for row in range(3):
                    self.event_id_dict["initial_stimuli"] = actr.schedule_event_relative(time,"add-text-to-exp-window",[None, self.initial_set_stimuli[self.current_block][row][:], {"x":self.my_x[row],"y":self.my_y[row]}])
            else:
                for row in range(6):
                    self.event_id_dict["initial_stimuli"] = actr.schedule_event_relative(time,"add-text-to-exp-window",[None, self.initial_set_stimuli[self.current_block][row][:], {"x":self.my_x[row],"y":self.my_y[row]}])


    def schedule_clear_screen(self,time):
        actr.schedule_event_relative(time,"clear-exp-window",priority=1,details="clr with 1")

    def schedule_next_stimulus(self,time):
        self.event_id_dict["next_stimulus"] = actr.schedule_event_relative(time,"modify-text-for-exp-window",[self.textIdDict["text_id"],{"text": self.initial_set_stimuli[self.current_block][self.sequence_num][:]}])
        self.sequence_num += 1

    def schedule_too_slow(self,time):
        self.event_id_dict["too_slow"] = actr.schedule_event_relative(time,"modify-text-for-exp-window",[self.textIdDict["text_id"],{"text": "TooSlow"}])

    def schedule_fixation_cross(self,time):
        self.event_id_dict["fixation_cross"] = actr.schedule_event_relative(time,"modify-text-for-exp-window",[self.textIdDict["text_id"],{"text": "+"}])

    def schedule_text(self,text,time):
        if text == "done":
            self.event_id_dict["done"] = actr.schedule_event_relative(time,"modify-text-for-exp-window",[self.textIdDict["text_id"],{"text": text}])
        else:
            actr.schedule_event_relative(time,"modify-text-for-exp-window",[self.textIdDict["text_id"],{"text": text}])
            # print(self.data)

    def experiment_cleanup(self):
        actr.remove_command_monitor("output-key","unit2-key-press")
        actr.remove_command("unit2-key-press")
        actr.call_command("delete-event-hook","my-event-hook")
        actr.remove_command("my-event-hook")

    def write_data(self, data_dir):
        out_data = pandas.DataFrame.from_dict(self.data)
        out_data['subject_num'] = self.subject_num
        out_data['condition'] = self.condition
        out_data.to_csv('{}/RLWM_{}_{}.csv'.format(data_dir, self.subject_num, self.condition), index=False)

# this is the original Collins (2018) testing condition (condtion == 1)
class RLWMTestRandom(RLWM):
    def __init__(self, maincsv_df, subject_num, condition):
        #open block_df.csv to get list of csv's in stim_path column.  (May not need ns/name columns)
        self.maincsv_df = pandas.read_csv(maincsv_df,header=0,usecols=["stimFile","corr_ans","ns"])
        self.initial_set_stimuli = pandas.concat([self.maincsv_df['stimFile'], self.maincsv_df['stimFile'], self.maincsv_df['stimFile'], self.maincsv_df['stimFile']], ignore_index=True)
        self.corr_ans_lists = pandas.concat([self.maincsv_df['corr_ans'], self.maincsv_df['corr_ans'], self.maincsv_df['corr_ans'], self.maincsv_df['corr_ans']], ignore_index=True)
        self.set_sizes = pandas.concat([self.maincsv_df['ns'], self.maincsv_df['ns'], self.maincsv_df['ns'], self.maincsv_df['ns']], ignore_index=True)
        #format the strings:  "stim/images6_animal/animal1.bmp" with "animal1" for example
        for j in range(len(self.initial_set_stimuli.index)):
            match = re.search('/(.+?)mp', self.initial_set_stimuli[j])
            match = re.search('/(.+?).b', match.group(1))
            self.initial_set_stimuli[j] = match.group(1)
        self.current_state = 0
        self.current_block = 0
        self.sequence_num = 0
        self.visicon_output = None
        #used for time start and end for script logging
        self.start = None
        self.end = None
        self.stim_substring = None
        self.window = None
        self.textIdDict = {
                "text_id": None
                }
        self.event_id_dict = {
                "next_stimulus": None,
                "too_slow": None,
                "fixation_cross": None,
                "initial_stimuli": None,
                "done": None
                }
        self.is_stim_vis = False
        self.initial_time = 0
        self.final_time = 0
        self.subject_num = subject_num
        self.condition = condition
        self.data = {
            "stimulus": [], # image/text shown
            "response": [], # key that was pressed, string NA if no response
            # we only care about responses to single images and not begin/end block
            "corr_response": [], # key that was correct
            "accuracy": [], # response == corr_response
            "rt": [], # response time (button_press_time - stim_start_time) or string NA if no response
            "block_num": [], # block number
            "set_size": []
        }
        # can write data with just
        # out_data = pandas.DataFrame.from_dict(self.data)
        # out_data['subject_num'] = self.subject_num
        # out_data['condition'] = self.condition
        # out_data.to_csv('RLWM_{}_{}.csv'.format(self.subject_num, self.condition))

    def write_data(self, data_dir):
        out_data = pandas.DataFrame.from_dict(self.data)
        out_data['subject_num'] = self.subject_num
        out_data['condition'] = self.condition
        out_data.to_csv('{}/RLWMTest_{}_{}.csv'.format(data_dir, self.subject_num, self.condition), index=False)

    def add_data(self,condition,key="NA"):
        self.data['set_size'].append(self.set_sizes[self.sequence_num-1])
        self.data["stimulus"].append(self.initial_set_stimuli[self.sequence_num-1][:])
        self.data["corr_response"].append(self.corr_ans_lists[self.sequence_num-1][:])
        self.data["block_num"].append(self.current_block + 1)
        if condition == "too_slow":
            self.data["response"].append("NA")
            self.data["accuracy"].append(int(0))  #<--- NA for Too Slow?
            self.data["rt"].append("NA")
        elif condition == "input_given":
            self.data["response"].append(key)
            self.data["accuracy"].append(int(key == self.corr_ans_lists[self.sequence_num-1][:]))
            self.data["rt"].append(actr.mp_time_ms() - self.initial_time)

    def post_event_hook(self, event_id):
        t1 = self
        if event_id == t1.event_id_dict["next_stimulus"]:
            t1.is_stim_vis = True
            logger.info("%s:state %s, post_event_hook():t1.event_id_dict[\"next_stimulus\"] triggered, event_id=%s" % ("{0:.2f}".format(t1.curr_time()),t1.current_state,event_id))
            #print("actr.mp_time_ms()=",actr.mp_time_ms())
            #actr.print_visicon()
            t1.initial_time = actr.mp_time_ms()
        elif event_id == t1.event_id_dict["too_slow"]:
            t1.is_stim_vis = False
            self.add_data("too_slow")
            logger.info("%s:state %s, Too Slow Event.  t1.sequence_num=%s" % ("{0:.2f}".format(self.curr_time()),t1.current_state,t1.sequence_num))
            #transition 2
            if t1.current_state == 2:
                t1.current_state = 4
                t1.schedule_fixation_cross(0)
                t1.schedule_next_stimulus(.5)
                t1.schedule_too_slow(2)
                logger.info("%s:state %s, Transition 2" % ("{0:.2f}".format(self.curr_time()),t1.current_state))
            #transition 4
            elif t1.current_state == 3 and not t1.block_finished():
                t1.current_state = 4
                logger.info("%s:state %s, Transition 4" % ("{0:.2f}".format(self.curr_time()),t1.current_state))
                t1.schedule_fixation_cross(0)
                t1.schedule_next_stimulus(.5)
                t1.schedule_too_slow(2)
            #transition 5
            elif t1.current_state == 3 and t1.block_finished() and not t1.all_blocks_finished():
                t1.current_state = 8
                logger.info("%s:state %s, Transition 5" % ("{0:.2f}".format(self.curr_time()),t1.current_state))
                t1.current_block += 1
                t1.schedule_text("done",0)
            #transition 7
            elif t1.current_state == 4 and not t1.block_finished():
                #don't change state
                logger.info("%s:state %s, Transition 7" % ("{0:.2f}".format(self.curr_time()),t1.current_state))
                t1.schedule_fixation_cross(0)
                t1.schedule_next_stimulus(.5)
                t1.schedule_too_slow(2)
            #transition 11
            elif t1.current_state == 3 and t1.block_finished() and t1.all_blocks_finished():
                t1.current_state = 7
                logger.info("%s:state %s, Transition 11" % ("{0:.2f}".format(self.curr_time()),t1.current_state))
                t1.schedule_text("ExperimentComplete",0)
            #transition 13
            elif t1.current_state == 4 and t1.block_finished() and t1.all_blocks_finished():
                t1.current_state = 7
                logger.info("%s:state %s, Transition 13" % ("{0:.2f}".format(self.curr_time()),t1.current_state))
                t1.schedule_text("ExperimentComplete",0)
            #transition 15
            elif t1.current_state == 4 and t1.block_finished() and not t1.all_blocks_finished():
                t1.current_state = 8
                logger.info("%s:state %s, Transition 15" % ("{0:.2f}".format(self.curr_time()),t1.current_state))
                t1.current_block += 1
                t1.schedule_text("done",0)
        elif event_id == t1.event_id_dict["done"]:
            if t1.current_state == 8:
                t1.current_state = 9
                logger.info("%s:state %s, Transition 16" % ("{0:.2f}".format(self.curr_time()),t1.current_state))

    def display_feedback(self, key):
        self.is_stim_vis = False
        self.add_data("input_given",key)
        # if (key == self.corr_ans_lists[self.current_block][self.sequence_num-1][:]):
        #     actr.modify_text_for_exp_window(self.textIdDict["text_id"],text="1",x=150,y=150)
        # else:
        #     actr.modify_text_for_exp_window(self.textIdDict["text_id"],text="0",x=150,y=150)

    def respond_to_key_press(self, model, key):
        t1 = self
        # print(self.current_state, key, self.is_stim_vis)

        #print("respond_to_key_press->actr.mp_time_ms()=",actr.mp_time_ms())
        #actr.print_visicon()
        #transition 0
        if t1.current_state == 0 and key == "space":
            t1.current_state = 2
            t1.clear_screen()
            # print("clear_screen()")
            t1.display_fixation()
            # print("t1.display_fixation()")
            t1.schedule_next_stimulus(0.5)
            # print("t1.schedule_next_stimulus(0.5)")
            t1.schedule_too_slow(2)
            logger.info("%s:state %s, Transition 0" % ("{0:.2f}".format(self.curr_time()),t1.current_state))
        #transition 1
        elif t1.current_state == 2 and t1.stimulus_visible():
            t1.current_state = 3
            t1.delete_event(t1.event_id_dict["too_slow"])
            t1.display_feedback(key)
            t1.schedule_fixation_cross(0)
            t1.schedule_next_stimulus(.5)
            t1.schedule_too_slow(2)
            logger.info("%s:state %s, Transition 1" % ("{0:.2f}".format(self.curr_time()),t1.current_state))
        #transition 3
        elif t1.current_state == 3 and t1.stimulus_visible() and not t1.block_finished():
            #don't change state
            t1.delete_event(t1.event_id_dict["too_slow"])
            t1.display_feedback(key)
            t1.schedule_fixation_cross(0)
            t1.schedule_next_stimulus(.5)
            t1.schedule_too_slow(2)
            logger.info("%s:state %s, Transition 3" % ("{0:.2f}".format(self.curr_time()),t1.current_state))
        #transition 6
        elif t1.current_state == 3 and t1.stimulus_visible() and t1.block_finished() and not t1.all_blocks_finished():
            t1.current_state = 8
            logger.info("%s:state %s, Transition 6" % ("{0:.2f}".format(self.curr_time()),t1.current_state))
            t1.delete_event(t1.event_id_dict["too_slow"])
            t1.display_feedback(key)
            t1.current_block += 1
            t1.schedule_text("done",0)
            logger.info("%s:state %s, Transition 6" % ("{0:.2f}".format(self.curr_time()),t1.current_state))
        #transition 8
        elif t1.current_state == 4 and t1.stimulus_visible() and t1.block_finished() and not t1.all_blocks_finished():
            t1.current_state = 8
            t1.delete_event(t1.event_id_dict["too_slow"])
            t1.display_feedback(key)
            t1.current_block += 1
            t1.schedule_text("done",0)
            logger.info("%s:state %s, Transition 8" % ("{0:.2f}".format(self.curr_time()),t1.current_state))
        #transition 9
        elif t1.current_state == 9 and key == "space":
            t1.clear_screen()
            t1.schedule_initial_stimuli(t1.set_sizes[t1.current_block],True)    #<-- when True, it displays immediately
            t1.current_state = 0
            t1.sequence_num = 0
            logger.info("%s:state %s, Transition 9" % ("{0:.2f}".format(self.curr_time()),t1.current_state))
        #transition 10
        elif t1.current_state == 4 and t1.stimulus_visible() and not t1.block_finished():
            t1.current_state = 3
            t1.delete_event(t1.event_id_dict["too_slow"])
            t1.display_feedback(key)
            t1.schedule_fixation_cross(0)
            t1.schedule_next_stimulus(.5)
            t1.schedule_too_slow(2)
            logger.info("%s:state %s, Transition 10" % ("{0:.2f}".format(self.curr_time()),t1.current_state))
        #transition 12
        elif t1.current_state == 3 and t1.block_finished() and t1.all_blocks_finished() and t1.stimulus_visible():
            t1.current_state = 7
            t1.delete_event(t1.event_id_dict["too_slow"])
            t1.display_feedback(key)
            t1.schedule_text("ExperimentComplete",0)
            logger.info("%s:state %s, Transition 12" % ("{0:.2f}".format(self.curr_time()),t1.current_state))
        #transition 14
        elif t1.current_state == 4 and t1.stimulus_visible() and t1.block_finished() and t1.all_blocks_finished():
            t1.current_state = 7
            t1.delete_event(t1.event_id_dict["too_slow"])
            t1.display_feedback(key)
            t1.schedule_text("ExperimentComplete",0)
            logger.info("%s:state %s, Transition 14" % ("{0:.2f}".format(self.curr_time()),t1.current_state))
        #Catch all for error debugging
        #else:
        #    logger.info("%s:state %s, No Matching Transitions!\nInputs:\nt1.stimulus_visible()=%s\nt1.block_finished()=%s\nt1.all_blocks_finished()=%s\nt1.visicon_output=%s\nself.textIdDict[\"text_id\"]=%s"
        #                % ("{0:.2f}".format(curr_time()),t1.current_state,t1.stimulus_visible(),t1.block_finished(),t1.all_blocks_finished(),t1.visicon_output,t1.textIdDict["text_id"]))

    def experiment_initialization(self, vis=False):
        # actr.reset()
        # actr.reload()
        actr.add_command("unit2-key-press", self.respond_to_key_press,
                         "Assignment 2 task output-key monitor")
        actr.add_command("my-event-hook", self.post_event_hook,
                         "called after an event")
        actr.monitor_command("output-key","unit2-key-press")
        actr.call_command("add-post-event-hook","my-event-hook")
        self.window = actr.open_exp_window("Leter difference task", visible=vis)
        # self.unpack_data()

    def schedule_next_stimulus(self,time):
        self.event_id_dict["next_stimulus"] = actr.schedule_event_relative(time,"modify-text-for-exp-window",[self.textIdDict["text_id"],{"text": self.initial_set_stimuli[self.sequence_num][:]}])
        self.sequence_num += 1

    def block_finished(self):
        #print("len(self.initial_set_stimuli[self.current_block].index)=",len(self.initial_set_stimuli[self.current_block].index)," (self.sequence_num + 1) =",(self.sequence_num + 1))
        return (self.sequence_num == len(self.initial_set_stimuli.index))

    def all_blocks_finished(self):
        #print("self.index_size=",self.index_size," (self.current_block)=",(self.current_block))
        return (self.current_block == 0)

    def schedule_initial_stimuli(self,time=0):
        self.event_id_dict["initial_stimuli"] = actr.schedule_event_relative(time,"add-text-to-exp-window",[self.window, "BeginTest", {"x":150,"y":150}])

def experiment(subject_num=999, condition=1, data_dir="."):
    if not os.path.isdir('{}'.format(data_dir)):
        os.mkdir('{}'.format(data_dir))
    t1 = RLWM("data/{}/block_df.csv".format(subject_num), subject_num, condition)
    t1.start = time.monotonic()
    t1.experiment_initialization(vis=False)
    #Initial Transition
    t1.schedule_initial_stimuli(t1.set_sizes[0],True)
    logger.info("%s:state %s, experiment():initial transition" % ("{0:.2f}".format(t1.curr_time()),t1.current_state))
    actr.install_device(t1.window)
    # actr.run(10, False) # debugging
    actr.run(1200,False)            #<-- run() blocks
    t1.write_data(data_dir)
    t1.experiment_cleanup()
    actr.remove_device(t1.window)
    t2 = RLWMTestRandom("data/{}/test_phase_random.csv".format(subject_num), subject_num, condition)
    t2.start = time.monotonic()
    t2.experiment_initialization(vis=False)
    # put up test in 7 minutes
    t2.schedule_initial_stimuli(7*60)
    # t2.schedule_initial_stimuli(0) # for debugging
    logger.info("%s:state %s, experiment():test initial transition" % ("{0:.2f}".format(t2.curr_time()),t2.current_state))
    actr.install_device(t2.window)
    # need to run for additional 7 minutes for OSPAN/NBack break
    actr.run(7*60+1200,False)            #<-- run() blocks
    # actr.run(20+7*60,False)            # debugging
    t2.write_data(data_dir)
    t2.experiment_cleanup()
    actr.remove_device(t2.window)

def run_subjects(subs, condition, data_dir):
    for sub in subs:
        experiment(sub, condition, data_dir)

def grid_search():
    ans_values = [.2, .3, .4, .5, .6, .7, .8]
    egs_values = [1, 2, 3]
    lf_values = [.1, .2, .3, .4]
    mas_values = [3, 4, 5]
    for ans_val in ans_values:
        for egs_val in egs_values:
            for lf_val in lf_values:
                for mas_val in mas_values:
                    with open("rlwm_model_nomeaning_template.lisp", 'r') as infile:
                        lines = infile.readlines()
                    with open("rlwm_model_nomeaning.lisp", 'w') as outfile:
                        for line in lines:
                            if line == "(bad-command)\n":
                                outfile.write("(sgp :ans {} :egs {} :lf {} :mas {})\n".format(ans_val, egs_val, lf_val, mas_val))
                            else:
                                outfile.write(line)
                    actr.load_act_r_model(os.path.abspath("rlwm_model_nomeaning.lisp").replace('/', ';')[1:])
                    data_dir = "fit_ans{}_egs{}_lf{}_mas{}_RLWM".format(ans_val, egs_val, lf_val, mas_val)
                    # actr.set_parameter_value(":ans", ans_val)
                    # actr.set_parameter_value(":egs", egs_val)
                    # actr.set_parameter_value(":lf", lf_val)
                    # actr.set_parameter_value(":mas", mas_val)
                    run_subjects(range(101, 121), 1, data_dir)
