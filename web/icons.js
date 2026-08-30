/* Glyphs for onX's 95 markup icons.
   Deliberately NOT onX's own artwork: their icon designs are proprietary, and
   bundling them into a third-party tool is a licensing question we don't need to
   take on. These are Unicode glyphs chosen to carry the same meaning, always
   shown alongside onX's exact text label so there is no ambiguity about which
   onX icon you are actually setting. */
const ONX_GLYPHS = {
  "4x4": "🚙", "ATV": "🏍️", "Access Point": "🚪", "Backpacker": "🎒",
  "Barrier": "🚧", "Beach Combing": "🏖️", "Bike": "🚲", "Camp": "⛺",
  "Camp Area": "🏕️", "Camp Backcountry": "⛺", "Campground": "🏕️",
  "Canoe": "🛶", "Cave": "🕳️", "Caving": "🕳️", "Climbing": "🧗",
  "Closed Gate": "🚫", "Cornice": "🏔️", "Couloir": "🎿", "Crossing": "↔️",
  "Dirt Bike": "🏍️", "Dog Sledding": "🛷", "Eagle": "🦅",
  "Emergency Phone": "☎️", "Feeding Area": "🌾", "Fish": "🐟",
  "Food Source": "🍎", "Food Storage": "🥫", "Footbridge": "🌉",
  "Foraging": "🍄", "Fuel": "⛽", "Gate": "🚪", "Gear": "⚙️", "Geyser": "♨️",
  "Hand Launch": "🛶", "Hang Gliding": "🪂", "Hazard": "⚠️", "Hike": "🥾",
  "Horseback": "🐴", "Hot Spring": "♨️", "House": "🏠", "Kayak": "🛶",
  "Kennels": "🐕", "Lighthouses": "🗼", "Location": "📍", "Log Obstacle": "🪵",
  "Lookout": "🔭", "Marina": "⚓", "Mountain Biking": "🚵",
  "Mountaineer": "🧗", "Mushroom": "🍄", "Observation Towers": "🗼",
  "Open Gate": "🔓", "Overland": "🚐", "Parking": "🅿️", "Photo": "📷",
  "Picnic Area": "🧺", "Potable Water": "🚰", "Put In": "🛶", "RV": "🚐",
  "Raft": "🛟", "Rapids": "🌊", "Rappel": "🪢", "Road Barrier": "🚧",
  "Ruins": "🏛️", "SUV": "🚙", "Sasquatch": "🦶", "Shelter": "🛖", "Ski": "⛷️",
  "Ski Areas": "🎿", "Ski Touring": "⛷️", "Skin Track": "🎿",
  "Slide Path": "🏔️", "Snow Pit": "❄️", "Snowboarder": "🏂",
  "Snowmobile": "🛷", "Snowpark": "🏂", "Steep Trail": "⛰️",
  "Stock Tank": "🛢️", "Summit": "🏔️", "Surfing Area": "🏄", "Swimming": "🏊",
  "Take Out": "🛶", "Trailhead": "🥾", "Truck": "🛻", "View": "👁️",
  "Visitor Center": "ℹ️", "Washout": "🌊", "Water Crossing": "💧",
  "Water Source": "💧", "Waterfall": "🌊", "Webcam": "📹", "Wetland": "🦆",
  "Wildflower": "🌸", "Windsurfing": "🏄", "XC Skiing": "⛷️",
};
const glyph = name => ONX_GLYPHS[name] || "📍";
