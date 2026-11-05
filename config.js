/* =========================================================
   BUSINESS DETAILS: edit this file only.
   Every phone link, WhatsApp button, address and map on the
   site reads from here.
   ========================================================= */
window.SITE = {
  name: "Al-Fatah Marketing",

  // Phone shown to visitors, and the same number in international format (digits only, with country code)
  phoneDisplay: "+92 300 819 7052",
  phoneIntl: "923008197052",

  // WhatsApp number: international format, digits only, no "+" or spaces (e.g. 919876543210 for India)
  whatsapp: "923008197052",
  whatsappGreeting: "Hi Al-Fatah Marketing! I found you on your website and I'd like some help with a property.",

  email: "info@alfatah-marketing.com",

  // Social pages (footer icons). Use the full page links.
  facebook: "https://www.facebook.com/share/1FCS4tEiaN/",
  instagram: "https://www.instagram.com/alfatah_marketing",

  // Floating "Message us" button. Best: "https://m.me/<your-page-username>" so it opens a chat directly.
  // If left empty, it opens the Facebook page above (visitors then tap "Message").
  messenger: "",

  // Google Business Profile link, and the "write a review" link
  // (Business Profile → "Ask for reviews" → copy link). If reviewLink is empty, the profile link is used.
  googleProfile: "https://share.google/TXK2oh74nVRp27pmk",
  googleReview: "",

  // Office address (each line appears on its own line)
  addressLines: ["Ghosia Colony, 2 km Kattar Band Road", "Thokar Niaz Baig, Lahore 53700"],

  // What Google Maps should search for to show your office pin
  mapQuery: "Ghosia Colony, Kattar Band Road, Thokar Niaz Baig, Lahore, Pakistan",

  hours: [
    ["Monday – Sunday", "9:00 AM – 9:00 PM"]
  ]
};

/* Instant price estimate: rough plot price PER MARLA for each area (in rupees).
   These are sample figures. Update them to the rates you see in the market. */
window.SITE.estimateAreas = [
  ["Thokar Niaz Baig", 900000],
  ["Raiwind Road", 800000],
  ["Lake City", 2100000],
  ["Bahria Town", 1800000],
  ["Johar Town", 3500000],
  ["DHA Lahore", 2800000],
  ["Gulberg", 7000000]
];

/* Where form submissions are emailed. Create a free form at https://formspree.io,
   then paste its endpoint here, e.g. "https://formspree.io/f/abcdwxyz".
   Leave empty while testing: forms will show a success message but send nothing. */
window.SITE.formEndpoint = "https://formspree.io/f/mwllovdp";
