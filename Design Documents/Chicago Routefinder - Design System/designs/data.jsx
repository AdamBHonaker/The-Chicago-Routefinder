// Shared mock data for the CTA Transit PWA redesigns.
// Mirrors the shape the backend returns (see App.jsx).

const LINE_COLORS = {
  Red:    "#c60c30",
  Blue:   "#00a1de",
  Brown:  "#62361b",
  Green:  "#009b3a",
  Orange: "#f9461c",
  Purple: "#522398",
  Pink:   "#e27ea6",
  Yellow: "#f9e300",
};

// Mock routes from Logan Square → Art Institute (a realistic CTA trip)
const MOCK_RESULT = {
  recommendation:
    "Take the Blue Line from Logan Square toward the Loop. Get off at Monroe, then walk 4 minutes east through Millennium Park to the Art Institute. Total time is about 27 minutes. The next train arrives in 3 minutes.",
  origin: "Logan Square",
  destination: "Art Institute of Chicago",
  originSub: "CTA Blue Line Station",
  destSub: "111 S Michigan Ave",
  alerts: [
    {
      id: "a1",
      headline: "Elevator out of service at Jackson Red Line",
      impact: "Accessibility",
      level: "minor",
    },
    {
      id: "a2",
      headline: "Weekend Red Line work — Howard to Belmont single tracking",
      impact: "Delays 10–15 min",
      level: "major",
    },
  ],
  routes: [
    {
      id: "r1",
      total: 27,
      wait: 3,
      transfers: 0,
      walkMin: 4,
      legs: [
        { type: "walk", from: "Your location", to: "Logan Square", minutes: 2, blocks: "1 short block" },
        {
          type: "transit",
          line: "Blue",
          code: "BL",
          from: "Logan Square",
          to: "Monroe",
          minutes: 21,
          stops: 8,
          wait: 3,
          direction: "Toward Forest Park",
          heading: "O'Hare-bound",
        },
        { type: "walk", from: "Monroe", to: "Your destination", minutes: 4, exit: "Monroe & Dearborn (NE corner)" },
      ],
    },
    {
      id: "r2",
      total: 32,
      wait: 1,
      transfers: 1,
      walkMin: 6,
      legs: [
        { type: "walk", from: "Your location", to: "Logan Square", minutes: 2 },
        {
          type: "transit",
          line: "Blue",
          code: "BL",
          from: "Logan Square",
          to: "Jackson",
          minutes: 19,
          stops: 7,
          wait: 1,
        },
        { type: "walk", from: "Jackson (Blue)", to: "Jackson (Red)", minutes: 3 },
        {
          type: "transit",
          line: "Red",
          code: "RD",
          from: "Jackson",
          to: "Monroe",
          minutes: 2,
          stops: 1,
          wait: 4,
        },
        { type: "walk", from: "Monroe", to: "Your destination", minutes: 5 },
      ],
    },
    {
      id: "r3",
      total: 34,
      wait: 0,
      transfers: 1,
      walkMin: 3,
      legs: [
        { type: "walk", from: "Your location", to: "Logan & Milwaukee", minutes: 1 },
        {
          type: "transit",
          line: "Bus",
          code: "76",
          lineName: "76 Diversey",
          from: "Logan & Milwaukee",
          to: "Clark & Diversey",
          minutes: 14,
          wait: 0,
          direction: "Eastbound",
        },
        {
          type: "transit",
          line: "Brown",
          code: "BR",
          from: "Diversey",
          to: "Washington/Wells",
          minutes: 16,
          stops: 9,
          wait: 5,
        },
        { type: "walk", from: "Washington/Wells", to: "Your destination", minutes: 3 },
      ],
    },
  ],
};

const SAVED_PLACES = [
  { id: "home", label: "Home", sub: "2132 N Kedzie Blvd", icon: "home" },
  { id: "work", label: "Work", sub: "Merchandise Mart", icon: "work" },
  { id: "gym",  label: "Chicago Athletic", sub: "12 S Michigan Ave", icon: "star" },
  { id: "mom",  label: "Mom's", sub: "Rogers Park", icon: "heart" },
];

const RECENT_TRIPS = [
  { id: "t1", from: "Home", to: "Merchandise Mart", when: "This morning" },
  { id: "t2", from: "Wicker Park", to: "O'Hare Terminal 2", when: "Saturday" },
  { id: "t3", from: "Home", to: "Wrigley Field", when: "Apr 14" },
];

// Live-trip mock (user is on Blue Line toward Monroe)
const LIVE_TRIP = {
  route: "r1",
  line: "Blue",
  currentStop: "Division",
  nextStop: "Chicago",
  stopsRemaining: 5,
  minutesToArrival: 14,
  minutesToExit: 18,
  stops: [
    { name: "Logan Square", status: "past" },
    { name: "California", status: "past" },
    { name: "Western", status: "past" },
    { name: "Damen", status: "past" },
    { name: "Division", status: "current" },
    { name: "Chicago", status: "upcoming" },
    { name: "Grand", status: "upcoming" },
    { name: "Clark/Lake", status: "upcoming" },
    { name: "Washington", status: "upcoming" },
    { name: "Monroe", status: "exit" },
  ],
};

Object.assign(window, { LINE_COLORS, MOCK_RESULT, SAVED_PLACES, RECENT_TRIPS, LIVE_TRIP });
