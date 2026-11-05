/* =========================================================
   PROPERTY LISTINGS: add, remove or edit properties here.
   type:  house | apartment | plot | commercial
   price: full amount in rupees (e.g. 2.5 crore = 25000000)
   marla: size in marla (20 marla = 1 kanal). For apartments, use sqft instead.
   img:   any image URL, or a local file like "images/my-house.jpg"
   ========================================================= */
window.LISTINGS = [
  {
    id: "AF-2048", title: "1 Kanal Modern House", location: "DHA Phase 6, Lahore", type: "house",
    price: 95000000, marla: 20, beds: 5, baths: 6, badge: "Featured", hot: true,
    img: "https://images.unsplash.com/photo-1600596542815-ffad4c1539a9?w=900&q=80",
    desc: "Brand-new modern design with double-height lounge, Italian kitchen, home theatre, basement and fully solar-powered backup.",
    features: ["Basement", "Solar system", "Home theatre", "Servant quarter", "Double-height lounge"]
  },
  {
    id: "AF-2051", title: "10 Marla Family House", location: "Bahria Town, Lahore", type: "house",
    price: 38500000, marla: 10, beds: 5, baths: 5, badge: "New",
    img: "https://images.unsplash.com/photo-1570129477492-45c003edd2be?w=900&q=80",
    desc: "Spacious house near the park and mosque, with a lawn, car porch for two cars and a separate drawing/dining area.",
    features: ["Near park", "Lawn", "2-car porch", "Gas available", "Possession ready"]
  },
  {
    id: "AF-2055", title: "2 Bed Luxury Apartment", location: "Gulberg III, Lahore", type: "apartment",
    price: 29000000, sqft: 1350, beds: 2, baths: 2, badge: "Hot deal", hot: true,
    img: "https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?w=900&q=80",
    desc: "High-rise apartment with city views, 24/7 security, lifts, backup generator and reserved basement parking.",
    features: ["City view", "24/7 security", "Lifts", "Generator backup", "Basement parking"]
  },
  {
    id: "AF-2060", title: "5 Marla House", location: "Thokar Niaz Baig, Lahore", type: "house",
    price: 16500000, marla: 5, beds: 3, baths: 3, badge: "Near office",
    img: "https://images.unsplash.com/photo-1564013799919-ab600027ffc6?w=900&q=80",
    desc: "Well-built double-storey house close to Kattar Band Road and the motorway, ideal for a small family.",
    features: ["Double storey", "Near motorway", "Corner", "Gas & electricity"]
  },
  {
    id: "AF-2063", title: "10 Marla Residential Plot", location: "Lake City, Lahore", type: "plot",
    price: 21000000, marla: 10, badge: "Plot",
    img: "https://images.unsplash.com/photo-1500382017468-9049fed747ef?w=900&q=80",
    desc: "Possession-ready plot on a 40 ft road, all dues clear, close to the main boulevard and commercial area.",
    features: ["Possession ready", "All dues clear", "40 ft road", "Near boulevard"]
  },
  {
    id: "AF-2070", title: "4 Marla Commercial Plot", location: "Raiwind Road, Lahore", type: "commercial",
    price: 32000000, marla: 4, badge: "Commercial",
    img: "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?w=900&q=80",
    desc: "Main-road commercial plot with high footfall, approved for a plaza, ideal for shops and offices.",
    features: ["Main road", "Plaza approved", "High footfall", "Investment"]
  }
];
