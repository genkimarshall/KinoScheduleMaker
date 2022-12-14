EMPLOYEE_INFO = { # Tuples: (is full-time?, 'Department Name').
  'A1': (False, 'SD'),
  'B1': (False, 'CASHIER'),
  'D1': (False, 'NBC'),
  'E1': (False, 'CASHIER'),
  'G1': (False, 'NBC'),
  'J1': (False, 'SD'),
  'J2': (False, 'EB'),
  'J3': (False, 'CB'),
  'J4': (False, 'EB'),
  'K1': (False, 'NBC'),
  'K2': (False, 'EB'),
  'K3': (True,  'OTHER'),
  'M1': (True,  'SD'),
  'M2': (False, 'CASHIER'),
  'M3': (False, 'JB'),
  'M4': (False, 'CASHIER'),
  'M5': (False, 'SD'),
  'M6': (True,  'EB'),
  'N1': (True,  'OTHER'),
  'P1': (False, 'EB'),
  'R1': (False, 'SD'),
  'R2': (False, 'JB'),
  'S1': (False, 'OTHER'),
  'T1': (False, 'SD'),
  'T2': (True,  'NBC'),
  'Y1': (False, 'JB'),
}

SCHEDULE = { # Tuples: (shift, name). Shift can be one of: 'E', 'M', 'L', or 'starttime-endtime'.
  0: [ # Monday.
    ('E', 'M1'),
    ('E', 'K3'),
    ('E', 'M6'),
    ('E', 'S1'),
    ('E', 'J2'),
    ('E', 'R2'),
    ('L', 'N1'),
    ('L', 'M3'),
    ('L', 'J3'),
    ('L', 'R1'),
    ('L', 'Y1'),
    ('L', 'P1'),
    ('M', 'M2'),
    ('E', 'D1'),
    ('L', 'T2'),
  ],
  1: [ # Tuesday.
    ('E', 'M6'),
    ('E', 'S1'),
    ('E', 'J1'),
    ('E', 'J2'),
    ('E', 'K2'),
    ('E', 'P1'),
    ('M', 'M4'),
    ('L', 'N1'),
    ('L', 'M1'),
    ('L', 'M5'),
    ('L', 'R2'),
    ('L', 'J4'),
    ('L', 'A1'),
    ('L', 'Y1'),
    ('E', 'T2'),
    ('M', 'K1'),
    ('L', 'G1'),
  ],
  2: [ # Wednesday.
    ('E', 'K3'),
    ('E', 'M6'),
    ('E', 'S1'),
    ('E', 'A1'),
    ('E', 'B1'),
    ('M', 'M4'),
    ('L', 'M1'),
    ('L', 'J1'),
    ('L', 'J4'),
    ('L', 'J2'),
    ('E', 'T2'),
    ('L', 'D1'),
  ],
  3: [ # Thursday.
    ('E', 'M1'),
    ('E', 'S1'),
    ('E', 'M3'),
    ('E', 'R1'),
    ('E', 'Y1'),
    ('M', 'J1'),
    ('M', 'M4'),
    ('L', 'K3'),
    ('L', 'M6'),
    ('L', 'R2'),
    ('L', 'K2'),
    ('L', 'B1'),
    ('E', 'K1'),
    ('M', 'G1'),
    ('L', 'T2'),
  ],
  4: [ # Friday.
    ('E', 'N1'),
    ('L', 'K3'),
    ('E', 'R1'),
    ('E', 'J4'),
    ('E', 'A1'),
    ('E', 'K2'),
    ('L', 'M2'),
    ('L', 'P1'),
    ('L', 'M5'),
    ('L', 'J3'),
    ('E', 'G1'),
    ('L', 'K1'),
  ],
  5: [ # Saturday.
    ('E', 'M5'),
    ('E', 'J3'),
    ('E', 'J4'),
    ('E', 'Y1'),
    ('E', 'M2'),
    ('M', 'B1'),
    ('L', 'N1'),
    ('L', 'M6'),
    ('L', 'A1'),
    ('L', 'K2'),
    ('L', 'T1'),
    ('L', 'E1'),
    ('E', 'T2'),
    ('L', 'K1'),
  ],
  6: [ # Sunday.
    ('E', 'M1'),
    ('E', 'M3'),
    ('E', 'J3'),
    ('E', 'P1'),
    ('10:00-5:00', 'M2'),
    ('L', 'N1'),
    ('L', 'K3'),
    ('L', 'R2'),
    ('L', 'J2'),
    ('E', 'T2'),
    ('L', 'G1'),
  ],
}

REGISTER_COUNT = { # List of tuples (desired register count, starting at what time).
  0: [ # Monday.
    (1, '10:00'),
    (2, '11:30'),
    (1, '6:30'),
  ],
  1: [ # Tuesday.
    (1, '10:00'),
    (2, '10:30'),
    (1, '7:30'),
  ],
  2: [ # Wednesday.
    (1, '10:00'),
    (2, '11:00'),
    (1, '7:00'),
  ],
  3: [ # Thursday.
    (1, '10:00'),
    (2, '12:00'),
    (1, '7:00'),
  ],
  4: [ # Friday.
    (1, '10:00'),
    (2, '12:00'),
  ],
  5: [ # Saturday.
    (1, '10:00'),
    (2, '10:30'),
    (3, '12:00'),
    (2, '6:30'),
  ],
  6: [ # Sunday.
    (1, '10:00'),
    (2, '11:00'),
    (3, '3:45'),
    (2, '5:15'),
  ],
}

MEETINGS = { # 'Name' -> List of tuples (start-time, end-time).
  0: { # Monday.
  },
  1: { # Tuesday.
  },
  2: { # Wednesday.
    'M6': [ ('11:00', '12:00'), ('6:00', '6:15') ],
  },
  3: { # Thursday.
  },
  4: { # Friday.
  },
  5: { # Saturday.
  },
  6: { # Sunday.
  },
}
