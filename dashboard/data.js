// ============================================================================
//  data.js  —  DATA DUMMY untuk Dashboard Reman JIM Sabah
//  ---------------------------------------------------------------------------
//  Semua angka di bawah adalah CONTOH sahaja (mengikut screenshot).
//  Bila data sebenar sedia, gantikan nilai di dalam objek REMAN_DATA sahaja —
//  struktur kekal sama, tiada perubahan perlu dibuat pada index.html.
// ============================================================================

const REMAN_DATA = {
  meta: {
    title: "DASHBOARD REMAN JIM SABAH",
    subtitle: "Iringkawal · Jabatan Imigresen Malaysia Sabah",
    refFrom: "02/01/2026",
    refTo: "26/11/2026",
    dummy: true,
  },

  // --- pilihan penapis ------------------------------------------------------
  options: {
    depot: ["Semua", "DIKK (Kota Kinabalu)", "DIP (Papar)"],
    warganegara: ["Semua", "Filipina", "Indonesia", "China", "Vietnam", "Pakistan", "Stateless", "Taiwan", "India", "Thailand"],
    akta: ["Semua", "Imigresen", "Dadah Berbahaya 1952", "Kanun Keseksaan", "Lain-lain", "ARJT", "Pertubuhan"],
    keseriusan: ["Semua", "Sangat Serius", "Serius", "Sederhana", "Ringan"],
    pegawai: ["Semua", "TBK HASRAH", "PI JAMIL", "PI JEVEN", "PI MOHD HAIKAL", "TBK FAIZAL", "PI AZIZI"],
    tindakan: ["Semua", "Usir", "Bebas", "Usir/BLI"],
  },

  // --- SECTION 2 : KPI ------------------------------------------------------
  kpi: {
    totalReman: 2114,
    nationalityPie: [
      { name: "Filipina", value: 82, color: "#0B2C4A" },
      { name: "Lain-lain", value: 18, color: "#F2B705" },
    ],
    usirRate: 97.1,
    usirDelta: 0.1,
    usirDeltaLabel: "dari Oktober",
    over14: 82,
    risk: [
      { name: "Paling Tinggi", value: 7, color: "#E5484D" },
      { name: "Tinggi", value: 1, color: "#F2762E" },
      { name: "Sederhana", value: 75, color: "#F2B705" },
      { name: "Rendah", value: 24, color: "#2E9E5B" },
    ],
    riskTotal: 107,
    severity: [
      { name: "Sangat Serius", value: 19, color: "#E5484D" },
      { name: "Serius", value: 446, color: "#F2762E" },
      { name: "Sederhana", value: 668, color: "#F2B705" },
      { name: "Ringan", value: 981, color: "#2E9E5B" },
    ],
  },

  // --- SECTION 3 : Profil banduan ------------------------------------------
  // Piramid jantina & kumpulan umur (Lelaki navy / Perempuan kuning)
  agePyramid: [
    { group: "60+", male: 235, female: 27 },
    { group: "45-59", male: 564, female: 57 },
    { group: "30-44", male: 610, female: 62 },
    { group: "18-29", male: 494, female: 40 },
  ],
  // Taburan umur (11 bin)
  ageDistribution: {
    labels: ["18-20", "21-23", "24-26", "27-29", "30-32", "33-35", "36-38", "39-41", "42-44", "45-47", "60+"],
    values: [92, 217, 232, 219, 237, 222, 238, 206, 188, 220, 43],
  },

  // --- SECTION 4 : Kesalahan x Warganegara ---------------------------------
  nationalityBars: [
    { name: "Filipina", value: 1727, color: "#F2B705" },
    { name: "Indonesia", value: 332, color: "#0B2C4A" },
    { name: "China", value: 20, color: "#0B2C4A" },
    { name: "Vietnam", value: 14, color: "#0B2C4A" },
    { name: "Pakistan", value: 6, color: "#0B2C4A" },
    { name: "Stateless", value: 6, color: "#0B2C4A" },
    { name: "Taiwan", value: 5, color: "#0B2C4A" },
    { name: "India", value: 3, color: "#0B2C4A" },
    { name: "Thailand", value: 1, color: "#0B2C4A" },
  ],
  // Treemap: warganegara (kotak besar) -> bangsa (kotak kecil)
  treemap: [
    { name: "FILIPINA", size: 1727, color: "#0B2C4A", children: [
      { name: "BAJAU", size: 900 }, { name: "SULUK", size: 320 }, { name: "VISAYA", size: 210 },
      { name: "KAGAYAN", size: 160 }, { name: "TAGALOG", size: 137 },
    ]},
    { name: "INDONESIA", size: 332, color: "#163E63", children: [
      { name: "BUGIS", size: 150 }, { name: "TIMOR", size: 100 }, { name: "JAWA", size: 82 },
    ]},
  ],

  // --- SECTION 5 : Tindakan & Pegawai --------------------------------------
  depotTrend: {
    labels: ["Jan", "Feb", "Mac", "Apr", "Mei", "Jun", "Jul", "Ogos", "Sep", "Okt", "Nov"],
    DIKK: [40, 55, 62, 58, 70, 66, 80, 92, 88, 96, 74],
    DIP:  [30, 42, 50, 45, 55, 52, 60, 68, 64, 70, 58],
  },
  // Beban kes vs kualiti data (bubble)
  bubbles: [
    { name: "TBK HASRAH", x: 129, y: 96, r: 24, cat: "Kritikal", color: "#E5484D" },
    { name: "PI JAMIL",   x: 105, y: 88, r: 20, cat: "Kritikal", color: "#E5484D" },
    { name: "PI JEVEN",   x: 98,  y: 74, r: 17, cat: "Tinggi",   color: "#F2762E" },
    { name: "PI M HAIKAL",x: 84,  y: 66, r: 15, cat: "Tinggi",   color: "#F2762E" },
    { name: "TBK FAIZAL", x: 76,  y: 58, r: 13, cat: "Sederhana",color: "#F2B705" },
    { name: "PI AZIZI",   x: 70,  y: 52, r: 12, cat: "Sederhana",color: "#F2B705" },
    { name: "TBK WANI",   x: 22,  y: 90, r: 8,  cat: "Tiada kes", color: "#2E9E5B" },
    { name: "TBK HERMAN", x: 18,  y: 84, r: 7,  cat: "Tiada kes", color: "#2E9E5B" },
  ],
  // Akta x kumpulan umur (% dalam setiap akta)
  aktaAge: {
    rows: ["Imigresen", "Dadah Berbahaya 1952", "Kanun Keseksaan", "Lain-lain", "ARJT", "Pertubuhan"],
    cols: ["18-29", "30-44", "45-59", "60+"],
    values: [
      [45, 38, 12, 5],
      [30, 40, 20, 10],
      [15, 35, 30, 20],
      [50, 30, 15, 5],
      [10, 40, 35, 15],
      [60, 25, 10, 5],
    ],
  },

  // --- SECTION 6 : Trend & Peta --------------------------------------------
  monthlyReman: {
    labels: ["Jan", "Feb", "Mac", "Apr", "Mei", "Jun", "Jul", "Ogos", "Sep", "Okt", "Nov"],
    baharu:   [180, 195, 210, 205, 220, 215, 230, 225, 240, 235, 214],
    lanjutan: [ 60,  70,  80,  75,  85,  82,  90,  95,  88,  92,  82],
  },
  // Peta asal warganegara -> JIM Sabah
  originMap: [
    { name: "Filipina",  lat: 12.88, lng: 121.77, count: 1727, akta: "Imigresen", color: "#F2B705" },
    { name: "Indonesia", lat: -2.50, lng: 118.00, count: 332,  akta: "Imigresen", color: "#0B2C4A" },
    { name: "China",     lat: 35.00, lng: 105.00, count: 20,   akta: "Imigresen", color: "#E5484D" },
    { name: "Vietnam",   lat: 14.06, lng: 108.28, count: 14,   akta: "Lain-lain", color: "#2E9E5B" },
    { name: "Pakistan",  lat: 30.37, lng: 69.35,  count: 6,    akta: "Lain-lain", color: "#F2762E" },
    { name: "India",     lat: 20.59, lng: 78.96,  count: 3,    akta: "Lain-lain", color: "#6B7A90" },
  ],
  jimSabah: { lat: 5.98, lng: 116.07, name: "JIM SABAH (Kota Kinabalu)" },
};
