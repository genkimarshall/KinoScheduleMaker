#!/usr/bin/env python3

import datetime
import time

import ortools.sat.python.cp_model as cp_model
import sty

GLOBAL_START_TIME = time.time()

def ranges_min_to_max(ranges):
  return range(min(r.start for r in ranges), max(r.stop for r in ranges))

class Store:
  TIME_OPEN = 10 # 10 AM
  TIME_CLOSE = 20 # 8 PM
  HOURS_OPEN = TIME_CLOSE - TIME_OPEN
  MINUTES_PER_SLOT = 15
  SLOTS_PER_HOUR = 60 // MINUTES_PER_SLOT
  NUM_SLOTS = HOURS_OPEN * SLOTS_PER_HOUR

  @classmethod
  def time_to_slot(cls, t): # @t: H:MM or HH:MM in [10AM, 8PM]
    split = t.index(':')
    hour = int(t[:split])
    if hour < 10:
      hour += 12
    minute = int(t[split + 1:])
    return ((hour - cls.TIME_OPEN) * cls.SLOTS_PER_HOUR) + (minute // cls.MINUTES_PER_SLOT)

  @classmethod
  def slot_to_time(cls, slot):
    hour = cls.TIME_OPEN + (slot // cls.SLOTS_PER_HOUR)
    if hour > 12:
      hour -= 12
    seconds = (slot % cls.SLOTS_PER_HOUR) * cls.MINUTES_PER_SLOT
    return f'{hour}:{seconds:02}'

class Shift:
  def __init__(self, config, is_fulltime):
    # self.time_range is really all that technically defines a Shift. However,
    # it's easier to reason about lunch_priority(), lunch_slots_strict(), and
    # break_lunch_order() in terms of whether the person is fulltime or not,
    # and what their "config" is (Early, Middle, or Late). Note that this
    # "config" can also be an arbitrary time-range (see example in config.py).
    self.config = config
    self.is_fulltime = is_fulltime
    if self.config in ['E', 'M', 'L']:
      t_start, t_stop = {
        ('E', True):  ('10:00', '6:30'),
        ('E', False): ('10:00', '5:45'),
        ('M', False): ('11:00', '7:00'),
        ('L', True):  ('11:15', '8:00'),
        ('L', False): ('12:00', '8:00'),
      }[config, is_fulltime]
    else:
      t_start, t_stop = self.config[:self.config.index('-')], self.config[self.config.index('-') + 1:]
    self.time_range = range(Store.time_to_slot(t_start), Store.time_to_slot(t_stop))

  def __eq__(self, other):
    return self.time_range == other.time_range

  @staticmethod
  def lunch_slots():
    return range(Store.time_to_slot('12:00'), Store.time_to_slot('4:00'), 4)

  def similar(self):
    if self.time_range.start < Store.time_to_slot('11:00'):
      return Shift('E', self.is_fulltime)
    elif self.time_range.stop < Store.time_to_slot('12:00'):
      return Shift('M', self.is_fulltime)
    else:
      return Shift('L', self.is_fulltime)

  def lunch_priority(self):
    if self.config not in ['E', 'M', 'L']:
      return self.similar().lunch_priority()
    return {
      ('E', True):  2,
      ('E', False): 2,
      ('M', False): 1,
      ('L', True):  0,
      ('L', False): 0,
    }[self.config, self.is_fulltime]

  def lunch_slots_strict(self):
    if self.config not in ['E', 'M', 'L']:
      return self.similar().lunch_slots_strict()
    t_start, t_stop = {
      ('E', True):  ('12:00', '2:00'),
      ('E', False): ('12:00', '2:00'),
      ('M', False): ('1:00', '3:00'),
      ('L', True):  ('2:00', '4:00'),
      ('L', False): ('2:00', '4:00'),
    }[self.config, self.is_fulltime]
    return range(Store.time_to_slot(t_start), Store.time_to_slot(t_stop), 4)

  def break_lunch_order(self, lunch_time):
    # 'L12': Lunch -> First Break -> Second Break.
    # '1L2': First Break -> Lunch -> Second Break.
    # '12L': First Break -> Second Break -> Lunch.
    if self.config not in ['E', 'M', 'L']:
      return self.similar().break_lunch_order(lunch_time)
    elif (lunch_time == '1:00') and (self.config == 'E'):
      return '1L2'
    elif (lunch_time == '2:00') and not (self.config == 'L' and not self.is_fulltime):
      return '1L2'
    elif lunch_time == '3:00':
      return '12L' if (self.config == 'E' and not self.is_fulltime) else '1L2'
    else:
      return 'L12'

class Appointment:
  # Using enum.Enum isn't worth adding .value everywhere.
  NOT_HERE = 0
  REGULAR = 1
  LUNCH = 2
  BREAK = 3
  CASHIER = 4
  SUPPORT = 5
  MEETING = 6
  COUNT = 7

  @classmethod
  def pretty_text(cls, val):
    return {
      cls.NOT_HERE: 'x',
      cls.REGULAR: ' ',
      cls.LUNCH: 'L',
      cls.BREAK: 'B',
      cls.CASHIER: 'C',
      cls.SUPPORT: 'S',
      cls.MEETING: 'M',
    }[val]

  @classmethod
  def pretty_color(cls, val):
    return {
      cls.NOT_HERE: sty.bg.black,
      cls.REGULAR: '',
      cls.LUNCH: sty.bg.li_blue,
      cls.BREAK: sty.bg.li_green,
      cls.CASHIER: '',
      cls.SUPPORT: sty.bg.li_yellow,
      cls.MEETING: sty.bg.li_magenta,
    }[val]

class Employee:
  def __init__(self, shift, name, dept):
    self.shift = shift
    self.name = name
    self.dept = dept

class Config:
  def __init__(self):
    import config as user_config
    day_of_week = datetime.datetime.today().weekday()
    self.employees = [
      Employee(
        Shift(shift_config, user_config.EMPLOYEE_INFO[e_name][0]),
        e_name,
        user_config.EMPLOYEE_INFO[e_name][1],
      ) for (shift_config, e_name) in user_config.SCHEDULE[day_of_week]
    ]
    self.meetings = {
      name: [
        range(Store.time_to_slot(meeting[0]), Store.time_to_slot(meeting[1]))
        for meeting in user_config.MEETINGS[day_of_week][name]
      ]
      for name in user_config.MEETINGS[day_of_week]
    }
    self.register_count = [{'count': x[0], 'start': Store.time_to_slot(x[1])} for x in user_config.REGISTER_COUNT[day_of_week]]

  def employee_ids(self, filt_type='ALL', opposite=False):
    if filt_type == 'ALL':
      return range(len(self.employees))
    elif filt_type == 'FULLTIME':
      return [eid for eid, emp in enumerate(self.employees) if opposite ^ emp.shift.is_fulltime]
    else:
      return [eid for eid, emp in enumerate(self.employees) if opposite ^ (emp.dept == filt_type)]

  def employee_name_to_id(self, name):
    ret = [eid for eid, emp in enumerate(self.employees) if emp.name == name]
    assert len(ret) != 0 # Software bug.
    if len(ret) == 1:
      return ret[0]
    else: # User error.
      raise SystemExit(f'Name "{name}" is not unique')

  def number_of_designated_cashiers_here(self, slot):
    count = 0
    for shift in [self.employees[eid].shift for eid in self.employee_ids('CASHIER')]:
      if slot in shift.time_range:
        count += 1
    return count

class SolutionPrinter(cp_model.CpSolverSolutionCallback):
  def __init__(self, run, stage):
    self.run = run
    self.stage = stage
    self.longest_name_len = len(max(self.run.config.employees, key=lambda x: len(x.name)).name)
    cp_model.CpSolverSolutionCallback.__init__(self)

  @staticmethod
  def gaps_between_breaks(emp, break1_slot, break2_slot, lunch_slot):
    shift_range = emp.shift.time_range
    ret = []
    prev_s = shift_range.start - 1
    for slot in sorted([break1_slot, break2_slot, lunch_slot, lunch_slot + 3, shift_range.stop]):
      ret.append(slot - prev_s - 1)
      prev_s = slot
    ret.remove(2) # The "gap" inside lunch doesn't count.
    return ret

  def print_gaps_between_breaks(self, eid, emp):
    breaks = [self.Value(self.run.sched[(eid, slot, Appointment.BREAK)]) for slot in range(Store.NUM_SLOTS)]
    break1_slot = breaks.index(True)
    break2_slot = breaks.index(True, break1_slot + 1)
    lunch_slot = ([self.Value(self.run.sched[(eid, slot, Appointment.LUNCH)]) for slot in range(Store.NUM_SLOTS)]).index(True)
    gaps = self.gaps_between_breaks(emp, break1_slot, break2_slot, lunch_slot)
    print(' gaps=[' + ','.join(f'{x:>2}' for x in gaps) + ']', end='')

  def num_slots_of_appointment(self, eid, appt):
    return [self.Value(self.run.sched[(eid, slot, appt)]) for slot in range(Store.NUM_SLOTS)].count(True)

  def print_employee_sched(self, eid):
    emp = self.run.config.employees[eid]
    print(f'{emp.name:{self.longest_name_len + 1}s}', end='')
    for slot in range(Store.NUM_SLOTS):
      if (slot % Store.SLOTS_PER_HOUR) == 0:
        print('|', end='')
      appointments = [self.Value(self.run.sched[(eid, slot, appt)]) for appt in range(Appointment.COUNT)]
      assert appointments.count(True) == 1
      appt = appointments.index(True)
      print(Appointment.pretty_color(appt) + Appointment.pretty_text(appt) + sty.fg.rs + sty.bg.rs, end='')
    num_cashier = self.num_slots_of_appointment(eid, Appointment.CASHIER)
    num_support = self.num_slots_of_appointment(eid, Appointment.SUPPORT)
    print(f' [C {num_cashier:>2}] [S {num_support:>2}]', end='')
    self.print_gaps_between_breaks(eid, emp)
    print(f' ({emp.dept})', end='')
    print()

  def print_slot_checksums(self, appointments):
    print(' ' * (self.longest_name_len + 2), end='')
    for slot in range(Store.NUM_SLOTS):
      if (slot != 0) and ((slot % Store.SLOTS_PER_HOUR) == 0):
        print('|', end='')
      print(sum(sum(self.Value(self.run.sched[(eid, slot, appt)]) for appt in appointments) for eid in self.run.config.employee_ids()), end='')

  def on_solution_callback(self):
    if self.stage == 0:
      print(f'Feasible constraint-set found! ({self.WallTime():.2f}s) ', end='')
      print(f'(Cost: {self.ObjectiveValue()}) ', end='')
      print(f'({sum(self.BooleanValue(c.enable) for c in self.run.soft_constraints)}/{len(self.run.soft_constraints)} constraints) ', end='')
      print('disabled=[', end='')
      print(','.join([c.name for c in self.run.soft_constraints if not self.BooleanValue(c.enable)]), end='')
      print(']')
    else:
      assert self.stage == 1
      print(f'Optimization found! ({self.WallTime():.2f}s) (Ideallism Cost: {self.ObjectiveValue()})')
    print(' ' * (self.longest_name_len + 2), end='')
    print('|'.join([f'{(time % 12):02}{"AM" if time < 12 else "PM"}' for time in range(Store.TIME_OPEN, Store.TIME_CLOSE)]))
    for eid in self.run.config.employee_ids():
      self.print_employee_sched(eid)
    self.print_slot_checksums([Appointment.CASHIER, Appointment.SUPPORT])
    print(' (checksum: register)')
    self.print_slot_checksums([Appointment.BREAK, Appointment.LUNCH])
    print(' (checksum: breakroom)')

class SoftConstraint:
  def __init__(self, model, name, weight, func):
    self.name = name
    self.weight = weight
    self.func = func
    self.enable = model.NewBoolVar(f'enable_{name}')

class Run:
  def __init__(self, config):
    self.config = config
    self.model = cp_model.CpModel()
    self.sched = {
      (eid, slot, appt): self.model.NewBoolVar(f'sched_e{eid}s{slot}a{appt}')
      for eid in self.config.employee_ids()
      for slot in range(Store.NUM_SLOTS)
      for appt in range(Appointment.COUNT)
    }
    self.add_hard_constraints()
    self.add_soft_constraints()
    self.setup_idealistic_objectives()

  def ortools_or(self, result, ortools_vars):
    # Experimentally, this way is faster than AddMaxEquality().
    self.model.AddBoolOr(ortools_vars + [result.Not()])
    for var in ortools_vars:
      self.model.AddImplication(var, result)

  def ortools_and(self, result, ortools_vars):
    # Experimentally, this way is faster than AddMinEquality().
    self.model.AddBoolOr([var.Not() for var in ortools_vars] + [result])
    for var in ortools_vars:
      self.model.AddImplication(result, var)

  def sched_index(self, eid, appt, last=False):
    # EXAMPLE:
    #   x = [0, 0, 1, 0, 0, 1, 0, 0] (len=8)
    #              2        5
    #   To get index of last "1":
    #     max(x[i] * i)
    #     max([0, 0, 2, 0, 0, 5, 0, 0])
    #     5
    #   To get index of first "1":
    #     len - max((len - i) * x[i])
    #     8 - max([8 * 0, 7 * 0, 6 * 1, 5 * 0, 4 * 0, 3 * 1, 2 * 0, 1 * 0])
    #     8 - max([0, 0, 6, 0, 0, 3, 0, 0])
    #     8 - 6
    #     2
    shift_range = self.config.employees[eid].shift.time_range
    appt_slot = self.model.NewIntVar(shift_range.start, shift_range.stop - 1, f'index_e{eid}a{appt}last{last}')
    if last:
      self.model.AddMaxEquality(appt_slot, [self.sched[(eid, slot, appt)] * slot for slot in shift_range])
    else:
      distance_from_end = self.model.NewIntVar(1, shift_range.stop - shift_range.start, f'distancefromend_e{eid}a{appt}last{last}')
      self.model.AddMaxEquality(distance_from_end,
        [self.sched[(eid, slot, appt)] * (shift_range.stop - slot) for slot in shift_range])
      self.model.Add(appt_slot == shift_range.stop - distance_from_end)
    return appt_slot

  def add_hard_constraints(self):
    # Hard Constraint: Shift start/end times, based on employee+shift.
    for eid in self.config.employee_ids():
      for slot in range(Store.NUM_SLOTS):
        here = slot in self.config.employees[eid].shift.time_range
        self.model.Add(self.sched[(eid, slot, Appointment.NOT_HERE)] == (not here))
    # Hard Constraint: Each employee has exactly one appointment per slot.
    for eid in self.config.employee_ids():
      for slot in range(Store.NUM_SLOTS):
        self.model.AddExactlyOne([self.sched[(eid, slot, appt)] for appt in range(Appointment.COUNT)])
    # Hard Constraint: Designated cashier is never regular/support/meeting.
    for eid in self.config.employee_ids():
      if eid in self.config.employee_ids('CASHIER'):
        for slot in range(Store.NUM_SLOTS):
          self.model.Add(self.sched[(eid, slot, Appointment.SUPPORT)] == 0)
          self.model.Add(self.sched[(eid, slot, Appointment.REGULAR)] == 0)
          self.model.Add(self.sched[(eid, slot, Appointment.MEETING)] == 0)
    # Hard Constraint: At least one cashier at all times.
    for slot in range(Store.NUM_SLOTS):
      self.model.AddAtLeastOne([self.sched[(eid, slot, Appointment.CASHIER)] for eid in self.config.employee_ids()])
    # Hard Constraint: Obey self.config.register_count.
    for slot in range(Store.NUM_SLOTS):
      curr_count = None
      for epoch in self.config.register_count:
        if slot < epoch['start']:
          break
        curr_count = epoch['count']
      num_designated = self.config.number_of_designated_cashiers_here(slot)
      if curr_count < num_designated:
        raise SystemExit(
          f'config.REGISTER_COUNT needs updating: At {Store.slot_to_time(slot)}, register_count is {curr_count}'
          f' but there are {num_designated} designated cashiers!')
      self.model.Add(sum(
        [self.sched[(eid, slot, Appointment.CASHIER)] for eid in self.config.employee_ids()] +
        [self.sched[(eid, slot, Appointment.SUPPORT)] for eid in self.config.employee_ids()]
        ) == curr_count)
    # Hard Constraint: Non-cashier shouldn't be made cashier at same time as another cashier.
    for slot in range(Store.NUM_SLOTS):
      non_cashier_cashiers = self.model.NewBoolVar(f'noncashiercashiers_s{slot}')
      self.ortools_or(non_cashier_cashiers,
        [self.sched[(eid, slot, Appointment.CASHIER)] for eid in self.config.employee_ids('CASHIER', opposite=True)])
      # Use Add(sum(...) = 1) because OnlyEnforceIf() doesn't work with AddExactlyOne() yet.
      self.model.Add(sum(self.sched[(eid, slot, Appointment.CASHIER)] for eid in self.config.employee_ids()) == 1).OnlyEnforceIf(non_cashier_cashiers)
    # Hard Constraint: Two breaks per employee.
    for eid in self.config.employee_ids():
      self.model.Add(sum(self.sched[(eid, slot, Appointment.BREAK)] for slot in range(Store.NUM_SLOTS)) == 2)
    # Hard Constraint: One lunch-hour per employee.
    for eid in self.config.employee_ids():
      self.model.Add(sum(self.sched[(eid, slot, Appointment.LUNCH)] for slot in range(Store.NUM_SLOTS)) == Store.SLOTS_PER_HOUR)
    # Hard Constraint: Employee gets one lunch, on the hour, from lunch_slots().
    for eid in self.config.employee_ids():
      lunch_slots = self.config.employees[eid].shift.lunch_slots()
      self.model.AddExactlyOne([self.sched[(eid, slot, Appointment.LUNCH)] for slot in lunch_slots])
      for slot in lunch_slots:
        to_the_right = self.model.NewBoolVar(f'totheright_e{eid}s{slot}')
        self.ortools_and(to_the_right,
          [self.sched[(eid, ss, Appointment.LUNCH)] for ss in range(slot + 1, slot + Store.SLOTS_PER_HOUR)])
        self.model.AddImplication(self.sched[(eid, slot, Appointment.LUNCH)], to_the_right)
    # Hard Constraint: Employee never starts off with lunch.
    for eid in self.config.employee_ids():
      shift_range = self.config.employees[eid].shift.time_range
      self.model.Add(self.sched[(eid, shift_range.start, Appointment.LUNCH)] == 0)
    # Hard Constraint: Obey self.config.meetings.
    for e_name, meetings in self.config.meetings.items():
      eid = self.config.employee_name_to_id(e_name)
      for slot in range(Store.NUM_SLOTS):
        in_meeting = any(slot in meeting for meeting in meetings)
        self.model.Add(self.sched[(eid, slot, Appointment.MEETING)] == int(in_meeting))
    for eid in self.config.employee_ids():
      if self.config.employees[eid].name not in self.config.meetings:
        for slot in range(Store.NUM_SLOTS):
          self.model.Add(self.sched[(eid, slot, Appointment.MEETING)] == 0)

  def available_when_here_if_mult(self, employee_ids, available_appointments, num_exceptions=0):
    if len(employee_ids) == 1:
      return
    shift_ranges = [self.config.employees[eid].shift.time_range for eid in employee_ids]
    if num_exceptions == 0:
      for slot in ranges_min_to_max(shift_ranges):
        self.model.AddAtLeastOne([self.sched[(eid, slot, appt)] for eid in employee_ids for appt in available_appointments]).OnlyEnforceIf(self.curr_soft_enable)
    else:
      exceptions = []
      for slot in ranges_min_to_max(shift_ranges):
        num_avail = sum(self.sched[(eid, slot, appt)] for eid in employee_ids for appt in available_appointments)
        not_avail = self.model.NewBoolVar(f'notavail_ids{employee_ids}s{slot}')
        self.model.Add(num_avail == 0).OnlyEnforceIf(not_avail).OnlyEnforceIf(self.curr_soft_enable)
        self.model.Add(num_avail > 0).OnlyEnforceIf(not_avail.Not()).OnlyEnforceIf(self.curr_soft_enable)
        exceptions.append(not_avail)
      self.model.Add(sum(exceptions) <= num_exceptions).OnlyEnforceIf(self.curr_soft_enable)

  def ban_register_for_nbc_if_alone(self):
    if len(self.config.employee_ids('NBC')) == 1:
      for slot in range(Store.NUM_SLOTS):
        self.model.Add(self.sched[(self.config.employee_ids('NBC')[0], slot, Appointment.CASHIER)] == 0).OnlyEnforceIf(self.curr_soft_enable)
        self.model.Add(self.sched[(self.config.employee_ids('NBC')[0], slot, Appointment.SUPPORT)] == 0).OnlyEnforceIf(self.curr_soft_enable)

  def ban_register_for_non_cashier_as_first_thing_in_day_if_not_opening(self):
    for eid in self.config.employee_ids():
      if eid in self.config.employee_ids('CASHIER'):
        continue
      shift_range = self.config.employees[eid].shift.time_range
      if shift_range.start == Store.time_to_slot('10:00'):
        continue
      for appt in [Appointment.CASHIER, Appointment.SUPPORT]:
        self.model.Add(self.sched[(eid, shift_range.start, appt)] == 0).OnlyEnforceIf(self.curr_soft_enable)

  def ban_simultaneous_break_lunch_for_subgroup(self, employee_ids):
    for slot in range(Store.NUM_SLOTS):
      # Use Add(sum(...) <= 1) because OnlyEnforceIf() doesn't work with AddAtMostOne() yet.
      self.model.Add(
        sum(self.sched[(eid, slot, appt)] for eid in employee_ids for appt in [Appointment.LUNCH, Appointment.BREAK])
        <= 1).OnlyEnforceIf(self.curr_soft_enable)

  def cap_non_cashier_appointment_delta(self, appointments, max_delta):
    def ignore_fairness(eid):
      return (eid in self.config.employee_ids('NBC')) and (len(self.config.employee_ids('NBC')) == 1)
    for eid1 in self.config.employee_ids('CASHIER', opposite=True):
      if ignore_fairness(eid1):
        continue
      for eid2 in self.config.employee_ids('CASHIER', opposite=True):
        if eid1 >= eid2:
          continue
        if ignore_fairness(eid2):
          continue
        e1_count = sum(self.sched[(eid1, slot, appt)] for slot in range(Store.NUM_SLOTS) for appt in appointments)
        e2_count = sum(self.sched[(eid2, slot, appt)] for slot in range(Store.NUM_SLOTS) for appt in appointments)
        # Experimentally, AddAbsEquality() has very poor performance, so use |x| <= y <=> and(x <= y, x >= -y).
        self.model.Add((e1_count - e2_count) <= max_delta).OnlyEnforceIf(self.curr_soft_enable)
        self.model.Add((e1_count - e2_count) >= -max_delta).OnlyEnforceIf(self.curr_soft_enable)

  def cap_register_in_span(self, cap, slot_span):
    for eid in self.config.employee_ids('CASHIER', opposite=True):
      shift_range = self.config.employees[eid].shift.time_range
      for slot_base in range(shift_range.start, shift_range.stop):
        self.model.Add(
          sum(self.sched[(eid, slot, appt)]
            for slot in range(slot_base, min(shift_range.stop, slot_base + slot_span))
            for appt in [Appointment.CASHIER, Appointment.SUPPORT]
          ) <= cap)

  def cap_simultaneous_appointments(self, appointments, cap):
    for slot in range(Store.NUM_SLOTS):
      self.model.Add(
        sum(self.sched[(eid, slot, appt)] for eid in self.config.employee_ids() for appt in appointments)
        <= cap).OnlyEnforceIf(self.curr_soft_enable)

  def require_aesthetics_and_break_symmetries(self):
    for eid1 in self.config.employee_ids('CASHIER', opposite=True):
      for eid2 in self.config.employee_ids('CASHIER', opposite=True):
        if (eid1 >= eid2) or (eid1 in self.config.employee_ids('NBC')) or (eid2 in self.config.employee_ids('NBC')):
          continue
        for slot_range in [range(Store.time_to_slot('12:00')), range(Store.time_to_slot('6:00'), Store.NUM_SLOTS)]:
          for slot1 in slot_range:
            for slot2 in slot_range:
              both_cashier = self.model.NewBoolVar(f'bothcashier_s1{slot1}s2{slot2}e1{eid1}e2{eid2}')
              self.ortools_and(both_cashier,
                [self.sched[(eid1, slot1, Appointment.CASHIER)], self.sched[(eid2, slot2, Appointment.CASHIER)]])
              self.model.AddImplication(both_cashier, slot1 < slot2).OnlyEnforceIf(self.curr_soft_enable)
        if self.config.employees[eid1].shift == self.config.employees[eid2].shift:
          e1_lunch_slot = self.sched_index(eid1, Appointment.LUNCH)
          e2_lunch_slot = self.sched_index(eid2, Appointment.LUNCH)
          self.model.Add(e1_lunch_slot <= e2_lunch_slot).OnlyEnforceIf(self.curr_soft_enable)
          same_lunch = self.model.NewBoolVar(f'samelunch_e1{eid1}e2{eid2}')
          self.model.Add(e1_lunch_slot == e2_lunch_slot).OnlyEnforceIf(same_lunch).OnlyEnforceIf(self.curr_soft_enable)
          self.model.Add(e1_lunch_slot != e2_lunch_slot).OnlyEnforceIf(same_lunch.Not()).OnlyEnforceIf(self.curr_soft_enable)
          for first_break in [True, False]:
            e1_s_break = self.sched_index(eid1, Appointment.BREAK, first_break)
            e2_s_break = self.sched_index(eid2, Appointment.BREAK, first_break)
            self.model.Add(e1_s_break <= e2_s_break).OnlyEnforceIf(same_lunch).OnlyEnforceIf(self.curr_soft_enable)

  def require_break_lunches_gap(self, gap):
    for eid in self.config.employee_ids():
      break1_slot = self.sched_index(eid, Appointment.BREAK)
      break2_slot = self.sched_index(eid, Appointment.BREAK, last=True)
      lunch_slot = self.sched_index(eid, Appointment.LUNCH)
      for delta in [break1_slot - break2_slot, break1_slot - lunch_slot, break2_slot - lunch_slot, break1_slot - (lunch_slot + 3), break2_slot - (lunch_slot + 3)]:
        # Experimentally, AddAbsEquality() has very poor performance, so do a workaround by checking sign.
        positive = self.model.NewBoolVar(f'positive_e{eid}delta{delta}')
        self.model.Add(delta > 0).OnlyEnforceIf(positive)
        self.model.Add(delta <= 0).OnlyEnforceIf(positive.Not())
        self.model.Add(delta > gap).OnlyEnforceIf(positive).OnlyEnforceIf(self.curr_soft_enable)
        self.model.Add(delta < -gap).OnlyEnforceIf(positive.Not()).OnlyEnforceIf(self.curr_soft_enable)

  def require_fair_lunch_order(self):
    for eid1 in self.config.employee_ids():
      for eid2 in self.config.employee_ids():
        e1_shift = self.config.employees[eid1].shift
        e2_shift = self.config.employees[eid2].shift
        if e1_shift.lunch_priority() <= e2_shift.lunch_priority():
          continue
        for slot1 in e1_shift.lunch_slots():
          for slot2 in e2_shift.lunch_slots():
            lunch_lunch = self.model.NewBoolVar(f'lunchlunch_e1{eid1}e2{eid2}s1{slot1}s2{slot2}')
            self.ortools_and(lunch_lunch, [self.sched[(eid1, slot1, Appointment.LUNCH)], self.sched[(eid2, slot2, Appointment.LUNCH)]])
            self.model.AddImplication(lunch_lunch, slot1 <= slot2).OnlyEnforceIf(self.curr_soft_enable)

  def require_lunches_balanced(self):
    for lunch_a, lunch_b in [('12:00', '1:00'), ('2:00', '3:00')]:
      count_a = sum(self.sched[(eid, Store.time_to_slot(lunch_a), Appointment.LUNCH)] for eid in self.config.employee_ids())
      count_b = sum(self.sched[(eid, Store.time_to_slot(lunch_b), Appointment.LUNCH)] for eid in self.config.employee_ids())
      # Experimentally, AddAbsEquality() has very poor performance, so use |x| <= y <=> and(x <= y, x >= -y).
      self.model.Add((count_a - count_b) <= 1).OnlyEnforceIf(self.curr_soft_enable)
      self.model.Add((count_a - count_b) >= -1).OnlyEnforceIf(self.curr_soft_enable)

  def require_min_gap_break_from_start_end(self, start_gap, end_gap):
    for eid in self.config.employee_ids():
      shift_range = self.config.employees[eid].shift.time_range
      for slot in range(shift_range.start + start_gap - 1):
        self.model.Add(self.sched[(eid, slot, Appointment.BREAK)] == 0).OnlyEnforceIf(self.curr_soft_enable)
      for slot in range(shift_range.stop - end_gap, shift_range.stop):
        self.model.Add(self.sched[(eid, slot, Appointment.BREAK)] == 0).OnlyEnforceIf(self.curr_soft_enable)

  def require_stricter_lunch_bounds(self):
    for eid in self.config.employee_ids():
      lunch_slots_strict = self.config.employees[eid].shift.lunch_slots_strict()
      # Use Add(sum(...) = 1) because OnlyEnforceIf() doesn't work with AddExactlyOne() yet.
      self.model.Add(sum(self.sched[(eid, slot, Appointment.LUNCH)] for slot in lunch_slots_strict) == 1).OnlyEnforceIf(self.curr_soft_enable)

  def add_soft_constraints(self):
    self.soft_constraints = [
      SoftConstraint(self.model, 'aesthetics',            1, self.require_aesthetics_and_break_symmetries),
      SoftConstraint(self.model, 'break-3',               2, lambda: self.cap_simultaneous_appointments([Appointment.BREAK], 3)),
      SoftConstraint(self.model, 'break-4',               3, lambda: self.cap_simultaneous_appointments([Appointment.BREAK], 4)),
      SoftConstraint(self.model, 'break-5',               4, lambda: self.cap_simultaneous_appointments([Appointment.BREAK], 5)),
      SoftConstraint(self.model, 'break-bound-gap-44',    4, lambda: self.require_min_gap_break_from_start_end(4, 4)),
      SoftConstraint(self.model, 'break-bound-gap-54',    2, lambda: self.require_min_gap_break_from_start_end(5, 4)),
      SoftConstraint(self.model, 'break-bound-gap-11',  999, lambda: self.require_min_gap_break_from_start_end(1, 1)),
      SoftConstraint(self.model, 'break-lunch-gap-3',    10, lambda: self.require_break_lunches_gap(3)),
      SoftConstraint(self.model, 'break-lunch-gap-4',     4, lambda: self.require_break_lunches_gap(4)),
      SoftConstraint(self.model, 'breakroom-4-if-12',     2, lambda: self.cap_simultaneous_appointments([Appointment.BREAK, Appointment.LUNCH], 4) if len(self.config.employee_ids()) <= 12 else None),
      SoftConstraint(self.model, 'breakroom-5',           3, lambda: self.cap_simultaneous_appointments([Appointment.BREAK, Appointment.LUNCH], 5)),
      SoftConstraint(self.model, 'breakroom-6',          10, lambda: self.cap_simultaneous_appointments([Appointment.BREAK, Appointment.LUNCH], 6)),
      SoftConstraint(self.model, 'breakroom-7',         999, lambda: self.cap_simultaneous_appointments([Appointment.BREAK, Appointment.LUNCH], 6)),
      SoftConstraint(self.model, 'cashier-diff-0',       10, lambda: self.cap_non_cashier_appointment_delta([Appointment.CASHIER], 0)),
      SoftConstraint(self.model, 'cashier-diff-1',       20, lambda: self.cap_non_cashier_appointment_delta([Appointment.CASHIER], 1)),
      SoftConstraint(self.model, 'cashier-diff-2',       30, lambda: self.cap_non_cashier_appointment_delta([Appointment.CASHIER], 2)),
      SoftConstraint(self.model, 'cashier-diff-3',       40, lambda: self.cap_non_cashier_appointment_delta([Appointment.CASHIER], 3)),
      SoftConstraint(self.model, 'cashier-diff-4',      999, lambda: self.cap_non_cashier_appointment_delta([Appointment.CASHIER], 4)),
      SoftConstraint(self.model, 'diff-break-cashiers',   8, lambda: self.ban_simultaneous_break_lunch_for_subgroup(self.config.employee_ids('CASHIER'))),
      SoftConstraint(self.model, 'fulltime-avail',        1, lambda: self.available_when_here_if_mult(self.config.employee_ids('FULLTIME'), [Appointment.REGULAR, Appointment.CASHIER, Appointment.SUPPORT])),
      SoftConstraint(self.model, 'lunch-4-if-16',         2, lambda: self.cap_simultaneous_appointments([Appointment.LUNCH], 4) if len(self.config.employee_ids()) <= 16 else None),
      SoftConstraint(self.model, 'lunch-balance',         1, self.require_lunches_balanced),
      SoftConstraint(self.model, 'lunch-fair-order',      2, self.require_fair_lunch_order),
      SoftConstraint(self.model, 'lunch-strict-bounds',  20, self.require_stricter_lunch_bounds),
      SoftConstraint(self.model, 'nbc-avail',             1, lambda: self.available_when_here_if_mult(self.config.employee_ids('NBC'), [Appointment.REGULAR])),
      SoftConstraint(self.model, 'nbc-avail-except-1',    4, lambda: self.available_when_here_if_mult(self.config.employee_ids('NBC'), [Appointment.REGULAR], num_exceptions=1)),
      SoftConstraint(self.model, 'nbc-avail-except-2',    8, lambda: self.available_when_here_if_mult(self.config.employee_ids('NBC'), [Appointment.REGULAR], num_exceptions=2)),
      SoftConstraint(self.model, 'nbc-avail-except-3',   12, lambda: self.available_when_here_if_mult(self.config.employee_ids('NBC'), [Appointment.REGULAR], num_exceptions=3)),
      SoftConstraint(self.model, 'nbc-avail-except-4',   20, lambda: self.available_when_here_if_mult(self.config.employee_ids('NBC'), [Appointment.REGULAR], num_exceptions=4)),
      SoftConstraint(self.model, 'nbc-diff-break',        4, lambda: self.ban_simultaneous_break_lunch_for_subgroup(self.config.employee_ids('NBC'))),
      SoftConstraint(self.model, 'nbc-no-reg-if-alone',   4, self.ban_register_for_nbc_if_alone),
      SoftConstraint(self.model, 'no-reg-first-thing',    4, self.ban_register_for_non_cashier_as_first_thing_in_day_if_not_opening),
      SoftConstraint(self.model, 'register-diff-0',      10, lambda: self.cap_non_cashier_appointment_delta([Appointment.CASHIER, Appointment.SUPPORT], 0)),
      SoftConstraint(self.model, 'register-diff-1',      20, lambda: self.cap_non_cashier_appointment_delta([Appointment.CASHIER, Appointment.SUPPORT], 1)),
      SoftConstraint(self.model, 'register-diff-2',      30, lambda: self.cap_non_cashier_appointment_delta([Appointment.CASHIER, Appointment.SUPPORT], 2)),
      SoftConstraint(self.model, 'register-diff-3',      40, lambda: self.cap_non_cashier_appointment_delta([Appointment.CASHIER, Appointment.SUPPORT], 3)),
      SoftConstraint(self.model, 'register-diff-4',     999, lambda: self.cap_non_cashier_appointment_delta([Appointment.CASHIER, Appointment.SUPPORT], 4)),
      SoftConstraint(self.model, 'register-max-4-in-16',  4, lambda: self.cap_register_in_span(4, 16)),
      SoftConstraint(self.model, 'register-max-6-in-16', 99, lambda: self.cap_register_in_span(6, 16)),
    ]
    for c in self.soft_constraints:
      self.curr_soft_enable = c.enable
      c.func()
    self.model.Minimize(sum(c.weight * c.enable.Not() for c in self.soft_constraints))

  @staticmethod
  def imbalances(order, shift_range, break1_slot, break2_slot, lunch_slot):
    def delta(a, b):
      return b - a
    def three_way_delta(a, b, c):
      return [delta(a, b), delta(a, c), delta(b, c)]
    return {
      'L12': three_way_delta(break1_slot - (lunch_slot + 3), break2_slot - break1_slot, shift_range.stop - break2_slot),
      '1L2': [delta(break1_slot - (shift_range.start - 1), lunch_slot - break1_slot),
              delta(break2_slot - (lunch_slot + 3), shift_range.stop - break2_slot)],
      '12L': three_way_delta(break1_slot - (shift_range.start - 1), break2_slot - break1_slot, lunch_slot - break2_slot),
    }[order]

  def ideally_distribute_breaks_and_lunches(self):
    for eid in self.config.employee_ids():
      break1_slot = self.sched_index(eid, Appointment.BREAK)
      break2_slot = self.sched_index(eid, Appointment.BREAK, last=True)
      lunch_slot = self.sched_index(eid, Appointment.LUNCH)
      lunch_at_t = {}
      for lunch_time in ['12:00', '1:00', '2:00', '3:00']:
        lunch_at_t[lunch_time] = self.model.NewBoolVar(f'lunchat_t{lunch_time}e{eid}')
        self.model.Add(lunch_slot == Store.time_to_slot(lunch_time)).OnlyEnforceIf(lunch_at_t[lunch_time])
        self.model.Add(lunch_slot != Store.time_to_slot(lunch_time)).OnlyEnforceIf(lunch_at_t[lunch_time].Not())
      shift = self.config.employees[eid].shift
      for lunch_time in ['12:00', '1:00', '2:00', '3:00']:
        order = shift.break_lunch_order(lunch_time)
        if order == 'L12':
          self.model.Add(lunch_slot < break1_slot).OnlyEnforceIf(lunch_at_t[lunch_time])
        elif order == '1L2':
          self.model.Add(break1_slot < lunch_slot).OnlyEnforceIf(lunch_at_t[lunch_time])
          self.model.Add(lunch_slot < break2_slot).OnlyEnforceIf(lunch_at_t[lunch_time])
        else:
          assert order == '12L'
          self.model.Add(break2_slot < lunch_slot).OnlyEnforceIf(lunch_at_t[lunch_time])
        for imbalance in self.imbalances(order, shift.time_range, break1_slot, break2_slot, lunch_slot):
          imbalance_base = self.model.NewIntVar(0, Store.NUM_SLOTS, f'imbalancebase_e{eid}l{lunch_time}i{imbalance}')
          self.model.AddAbsEquality(imbalance_base, imbalance)
          imbalance_clamped = self.model.NewIntVar(0, Store.NUM_SLOTS, f'imbalanceclamped_e{eid}l{lunch_time}i{imbalance}')
          self.model.AddMaxEquality(imbalance_clamped, [0, imbalance_base - 1])
          imbalance_to_min = self.model.NewIntVar(0, Store.NUM_SLOTS, f'imbalancetoemin_e{eid}l{lunch_time}i{imbalance}')
          self.model.Add(imbalance_to_min == imbalance_clamped).OnlyEnforceIf(lunch_at_t[lunch_time])
          self.model.Add(imbalance_to_min == 0).OnlyEnforceIf(lunch_at_t[lunch_time].Not())
          self.to_minimize_later.append(imbalance_to_min)

  def ideally_have_register_appts_in_groups(self):
    def minimize_not_in_group(eid, exactly_one_a, appt, slot, neighbor_slots):
      one_of_multiple = self.model.NewBoolVar(f'oneofmultiple_e{eid}a{appt}s{slot}')
      self.ortools_and(one_of_multiple, [self.sched[(eid, slot, appt)], exactly_one_a.Not()])
      no_neighbors = self.model.NewBoolVar(f'noneighbors_e{eid}a{appt}s{slot}')
      self.ortools_and(no_neighbors, [self.sched[(eid, neighbor_slot, appt)].Not() for neighbor_slot in neighbor_slots])
      not_in_group = self.model.NewBoolVar(f'lonelya_e{eid}a{appt}s{slot}')
      self.ortools_and(not_in_group, [one_of_multiple, no_neighbors])
      self.to_minimize_later.append(not_in_group)
    for eid in self.config.employee_ids('CASHIER', opposite=True):
      for appt in [Appointment.SUPPORT, Appointment.CASHIER]:
        num_a = self.model.NewIntVar(0, Store.NUM_SLOTS, f'numa_e{eid}')
        self.model.Add(num_a == sum(self.sched[(eid, slot, appt)] for slot in range(Store.NUM_SLOTS)))
        exactly_one_a = self.model.NewBoolVar(f'exactlyonea_e{eid}')
        self.model.Add(num_a == 1).OnlyEnforceIf(exactly_one_a)
        self.model.Add(num_a != 1).OnlyEnforceIf(exactly_one_a.Not())
        for slot in range(1, Store.NUM_SLOTS - 1):
          minimize_not_in_group(eid, exactly_one_a, appt, slot, [slot - 1, slot + 1])
        for edge_slot, neighbor_slot in [(0, 1), (Store.NUM_SLOTS - 1, Store.NUM_SLOTS - 2)]:
          minimize_not_in_group(eid, exactly_one_a, appt, edge_slot, [neighbor_slot])

  def ideally_have_breakroom_occupancy_under_five(self):
    for slot in range(Store.NUM_SLOTS):
      breakroom_over_four = self.model.NewBoolVar(f'breakroomoverfour_s{slot}')
      breakroom_occ = sum(self.sched[(eid, slot, appt)]
        for eid in self.config.employee_ids() for appt in [Appointment.BREAK, Appointment.LUNCH])
      self.model.Add(breakroom_occ >= 5).OnlyEnforceIf(breakroom_over_four)
      self.model.Add(breakroom_occ < 5).OnlyEnforceIf(breakroom_over_four.Not())
      self.to_minimize_later.append(breakroom_over_four)

  def setup_idealistic_objectives(self):
    self.to_minimize_later = []
    self.ideally_distribute_breaks_and_lunches()
    self.ideally_have_register_appts_in_groups()
    self.ideally_have_breakroom_occupancy_under_five()

  def make_schedule_idealistic(self, solver):
    assert self.model.HasObjective()
    self.model.Proto().ClearField('objective')
    assert not self.model.HasObjective()
    for constraint in self.soft_constraints:
      self.model.Add(constraint.enable == solver.Value(constraint.enable))
    for eid in self.config.employee_ids():
      for slot in range(Store.NUM_SLOTS):
        for appt in range(Appointment.COUNT):
          if appt == Appointment.REGULAR:
            continue
          self.model.AddHint(self.sched[(eid, slot, appt)], solver.BooleanValue(self.sched[(eid, slot, appt)]))
    self.model.Minimize(sum(self.to_minimize_later))
    solver.parameters.max_time_in_seconds = 60
    status = solver.Solve(self.model, SolutionPrinter(self, stage=1))
    assert status not in [cp_model.INFEASIBLE, cp_model.MODEL_INVALID]
    if status == cp_model.OPTIMAL:
      print('Found the optimal schedule! (Given the constraints.)')
    else:
      assert status in [cp_model.FEASIBLE, cp_model.UNKNOWN]
      print('Ran out of time.')

  def attempt_to_solve(self, solver):
    status = solver.Solve(self.model, SolutionPrinter(self, stage=0))
    if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
      if status == cp_model.OPTIMAL:
        print('Found the optimal set of feasible constraints under these assumptions!')
      else:
        print('Determined some set of feasible constraints, not necessarily the optimal one...')
      print('Now moving things around to make the schedule more idealistic...')
      self.make_schedule_idealistic(solver)
      return True
    elif status == cp_model.INFEASIBLE:
      print(f'Infeasible. ({solver.WallTime():.2f}s this set / {(time.time() - GLOBAL_START_TIME):.2f}s since start)')
      return False
    elif status == cp_model.UNKNOWN:
      print('Ran out of time.')
      return False
    else:
      assert status == cp_model.MODEL_INVALID
      raise SystemExit('Model is invalid. That is a bug! Exiting.')

def main():
  config = Config()
  run = Run(config)
  solver = cp_model.CpSolver()
  solver.parameters.max_time_in_seconds = 15
  solver.parameters.enumerate_all_solutions = False
  for disabled_constraints in [
    [],
    ['cashier-diff-0'],
    ['register-diff-0'],
    ['cashier-diff-0', 'register-diff-0'],
    ['cashier-diff-0', 'register-diff-0', 'cashier-diff-1'],
    ['cashier-diff-0', 'register-diff-0', 'register-diff-1'],
    ['cashier-diff-0', 'register-diff-0', 'cashier-diff-1', 'register-diff-1'],
  ]:
    per_run_constraints = [run.model.Add(c.enable == (c.name not in disabled_constraints)) for c in run.soft_constraints]
    print(f'Assuming all constraints except for {disabled_constraints}... ', end='', flush=True)
    if run.attempt_to_solve(solver):
      return
    for constraint in per_run_constraints:
      constraint.Proto().Clear()
  solver.parameters.max_time_in_seconds = 60
  print('Assuming nothing. Trying to enable whichever constraints we can... ', end='', flush=True)
  if run.attempt_to_solve(solver):
    return
  print('Two possibilities:')
  print('(A) The configuration is incorrect -- please double check it?')
  print('(B) There is a bug in the code -- sorry!')

if __name__ == '__main__':
  main()
