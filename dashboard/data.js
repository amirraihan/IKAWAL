// data.js — dijana daripada data/iringkawal_bpk2026.xlsx oleh dashboard/build_data.py
// Jangan edit manual; jalankan semula:  python dashboard/build_data.py
const REMAN_DATA = {
 "meta": {
  "title": "DASHBOARD REMAN JIM SABAH",
  "subtitle": "Iringkawal · Jabatan Imigresen Malaysia Sabah",
  "refFrom": "02/01/2026",
  "refTo": "24/11/2026",
  "dummy": false
 },
 "options": {
  "depot": [
   "Semua",
   "DIKK (Kota Kinabalu)",
   "DIP (Papar)"
  ],
  "warganegara": [
   "Semua",
   "Filipina",
   "Indonesia",
   "China",
   "Vietnam",
   "Pakistan",
   "Stateless",
   "Dusun",
   "Taiwan"
  ],
  "akta": [
   "Semua",
   "Imigresen",
   "Dadah Berbahaya 1952",
   "Kanun Keseksaan",
   "Lain-lain",
   "ARJT",
   "Pertubuhan"
  ],
  "keseriusan": [
   "Semua",
   "Sangat Serius",
   "Serius",
   "Sederhana",
   "Ringan"
  ],
  "pegawai": [
   "Semua",
   "TBK HASRAH",
   "PI JAMIL",
   "PI JEVEN",
   "PI MOHD HAIKAL",
   "TBK FAIZAL",
   "PI AZIZI",
   "TBK LUNA",
   "TBK HUFAZ",
   "TBK SITI NURAISYAH",
   "TBK FAHRI",
   "TBK NUR MASYITAH",
   "PI FURQAN",
   "PI SHAHRIR",
   "PI FIONA",
   "PIK BRENDON",
   "PI NASRUL",
   "PI HAZMIZAN",
   "PI YUSUF",
   "TBK HERMAN",
   "TBK SUSAN",
   "PI CLAUDIA CALSON",
   "PI CLAUDIA",
   "PI SHAHRUL",
   "TBK WANI",
   "PI TBK SUSAN"
  ],
  "tindakan": [
   "Semua",
   "Usir",
   "Bebas",
   "Usir/BLI"
  ]
 },
 "kpi": {
  "totalReman": 2114,
  "nationalityPie": [
   {
    "name": "Filipina",
    "value": 82,
    "color": "#0B2C4A"
   },
   {
    "name": "Lain-lain",
    "value": 18,
    "color": "#F2B705"
   }
  ],
  "usirRate": 96.9,
  "usirDelta": -0.7,
  "usirDeltaLabel": "dari Okt",
  "over14": 201,
  "risk": [
   {
    "name": "Paling Tinggi",
    "value": 7,
    "color": "#E5484D"
   },
   {
    "name": "Tinggi",
    "value": 1,
    "color": "#F2762E"
   },
   {
    "name": "Sederhana",
    "value": 75,
    "color": "#F2B705"
   },
   {
    "name": "Rendah",
    "value": 24,
    "color": "#2E9E5B"
   }
  ],
  "riskTotal": 107,
  "severity": [
   {
    "name": "Sangat Serius",
    "value": 7,
    "color": "#E5484D"
   },
   {
    "name": "Serius",
    "value": 13,
    "color": "#F2762E"
   },
   {
    "name": "Sederhana",
    "value": 1817,
    "color": "#F2B705"
   },
   {
    "name": "Ringan",
    "value": 277,
    "color": "#2E9E5B"
   }
  ]
 },
 "agePyramid": [
  {
   "group": "60+",
   "male": 236,
   "female": 27
  },
  {
   "group": "45-59",
   "male": 574,
   "female": 57
  },
  {
   "group": "30-44",
   "male": 617,
   "female": 62
  },
  {
   "group": "18-29",
   "male": 501,
   "female": 40
  }
 ],
 "ageDistribution": {
  "labels": [
   "18-20",
   "21-23",
   "24-26",
   "27-29",
   "30-32",
   "33-35",
   "36-38",
   "39-41",
   "42-44",
   "45-47",
   "48+"
  ],
  "values": [
   139,
   133,
   132,
   137,
   127,
   139,
   138,
   150,
   125,
   135,
   759
  ]
 },
 "nationalityBars": [
  {
   "name": "Filipina",
   "value": 1740,
   "color": "#F2B705"
  },
  {
   "name": "Indonesia",
   "value": 335,
   "color": "#0B2C4A"
  },
  {
   "name": "China",
   "value": 20,
   "color": "#0B2C4A"
  },
  {
   "name": "Vietnam",
   "value": 6,
   "color": "#0B2C4A"
  },
  {
   "name": "Pakistan",
   "value": 6,
   "color": "#0B2C4A"
  },
  {
   "name": "Stateless",
   "value": 5,
   "color": "#0B2C4A"
  },
  {
   "name": "Dusun",
   "value": 1,
   "color": "#0B2C4A"
  },
  {
   "name": "Taiwan",
   "value": 1,
   "color": "#0B2C4A"
  }
 ],
 "treemap": [
  {
   "name": "FILIPINA",
   "size": 1740,
   "color": "#0B2C4A",
   "children": [
    {
     "name": "BAJAU",
     "size": 1149
    },
    {
     "name": "SULUK",
     "size": 447
    },
    {
     "name": "VISAYA",
     "size": 63
    },
    {
     "name": "KAGAYAN",
     "size": 43
    },
    {
     "name": "TAGALOG",
     "size": 27
    },
    {
     "name": "BISAYA",
     "size": 5
    }
   ]
  },
  {
   "name": "INDONESIA",
   "size": 335,
   "color": "#163E63",
   "children": [
    {
     "name": "BUGIS",
     "size": 150
    },
    {
     "name": "TIMOR",
     "size": 130
    },
    {
     "name": "JAWA",
     "size": 18
    },
    {
     "name": "BUTON",
     "size": 14
    },
    {
     "name": "INDONESIA",
     "size": 9
    },
    {
     "name": "TATOR",
     "size": 7
    }
   ]
  },
  {
   "name": "CHINA",
   "size": 20,
   "color": "#1E4E7A",
   "children": [
    {
     "name": "CHINA",
     "size": 20
    }
   ]
  },
  {
   "name": "VIETNAM",
   "size": 6,
   "color": "#2F5B8A",
   "children": [
    {
     "name": "VIETNAM",
     "size": 6
    }
   ]
  }
 ],
 "depotTrend": {
  "labels": [
   "Jan",
   "Feb",
   "Mac",
   "Apr",
   "Mei",
   "Jun",
   "Jul",
   "Ogos",
   "Sep",
   "Okt",
   "Nov"
  ],
  "DIKK": [
   118,
   139,
   206,
   215,
   53,
   0,
   44,
   107,
   96,
   58,
   110
  ],
  "DIP": [
   118,
   21,
   0,
   0,
   100,
   196,
   146,
   58,
   109,
   192,
   27
  ]
 },
 "bubbles": [
  {
   "name": "TBK HASRAH",
   "x": 229,
   "y": 100,
   "r": 229,
   "cat": "Tiada kes",
   "color": "#2E9E5B"
  },
  {
   "name": "PI JAMIL",
   "x": 205,
   "y": 100,
   "r": 205,
   "cat": "Tiada kes",
   "color": "#2E9E5B"
  },
  {
   "name": "PI JEVEN",
   "x": 193,
   "y": 100,
   "r": 193,
   "cat": "Tiada kes",
   "color": "#2E9E5B"
  },
  {
   "name": "PI MOHD HAIKAL",
   "x": 163,
   "y": 100,
   "r": 163,
   "cat": "Tiada kes",
   "color": "#2E9E5B"
  },
  {
   "name": "TBK FAIZAL",
   "x": 156,
   "y": 100,
   "r": 156,
   "cat": "Tiada kes",
   "color": "#2E9E5B"
  },
  {
   "name": "PI AZIZI",
   "x": 155,
   "y": 100,
   "r": 155,
   "cat": "Tiada kes",
   "color": "#2E9E5B"
  },
  {
   "name": "TBK LUNA",
   "x": 143,
   "y": 100,
   "r": 143,
   "cat": "Tiada kes",
   "color": "#2E9E5B"
  },
  {
   "name": "TBK HUFAZ",
   "x": 132,
   "y": 100,
   "r": 132,
   "cat": "Tiada kes",
   "color": "#2E9E5B"
  }
 ],
 "aktaAge": {
  "rows": [
   "Imigresen",
   "Dadah Berbahaya 1952",
   "Kanun Keseksaan",
   "Lain-lain",
   "ARJT",
   "Pertubuhan"
  ],
  "cols": [
   "18-29",
   "30-44",
   "45-59",
   "60+"
  ],
  "values": [
   [
    25,
    32,
    30,
    12
   ],
   [
    26,
    32,
    29,
    12
   ],
   [
    29,
    29,
    36,
    7
   ],
   [
    24,
    28,
    24,
    24
   ],
   [
    33,
    67,
    0,
    0
   ],
   [
    17,
    17,
    33,
    33
   ]
  ]
 },
 "monthlyReman": {
  "labels": [
   "Jan",
   "Feb",
   "Mac",
   "Apr",
   "Mei",
   "Jun",
   "Jul",
   "Ogos",
   "Sep",
   "Okt",
   "Nov"
  ],
  "baharu": [
   236,
   160,
   206,
   215,
   153,
   196,
   190,
   165,
   205,
   250,
   137
  ],
  "lanjutan": [
   22,
   126,
   53,
   0,
   0,
   0,
   0,
   0,
   0,
   0,
   0
  ]
 },
 "originMap": [
  {
   "name": "Filipina",
   "lat": 12.88,
   "lng": 121.77,
   "count": 1740,
   "akta": "Imigresen",
   "color": "#F2B705"
  },
  {
   "name": "Indonesia",
   "lat": -2.5,
   "lng": 118.0,
   "count": 335,
   "akta": "Imigresen",
   "color": "#0B2C4A"
  },
  {
   "name": "China",
   "lat": 35.0,
   "lng": 105.0,
   "count": 20,
   "akta": "Imigresen",
   "color": "#6B7A90"
  },
  {
   "name": "Vietnam",
   "lat": 14.06,
   "lng": 108.28,
   "count": 6,
   "akta": "Imigresen",
   "color": "#6B7A90"
  },
  {
   "name": "Pakistan",
   "lat": 30.37,
   "lng": 69.35,
   "count": 6,
   "akta": "Imigresen",
   "color": "#6B7A90"
  },
  {
   "name": "Stateless",
   "lat": 3.14,
   "lng": 101.69,
   "count": 5,
   "akta": "Imigresen",
   "color": "#6B7A90"
  },
  {
   "name": "Taiwan",
   "lat": 23.7,
   "lng": 120.96,
   "count": 1,
   "akta": "Imigresen",
   "color": "#6B7A90"
  }
 ],
 "jimSabah": {
  "lat": 5.98,
  "lng": 116.07,
  "name": "JIM SABAH (Kota Kinabalu)"
 }
};
