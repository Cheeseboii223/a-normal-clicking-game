// Ported 1:1 from the original Kivy main.py

const MILESTONE_THRESHOLDS = [10, 50, 100, 200, 500, 1000, 5000, 10000, 15000, 20000, 30000, 40000, 50000, 75000, 100000, 250000, 500000, 1000000, 5000000, 10000000, 25000000, 50000000, 100000000, 250000000, 500000000, 1000000000, 2500000000, 5000000000, 10000000000];

const MILESTONE_MESSAGES = {
  10: 'wow nice your at 10',
  50: 'hey half way..... to 100....',
  100: 'hey atleast your not half way anymore',
  200: 'the button is officially scared of you',
  500: 'you won 500!.. nothing!',
  1000: '1k and still no prizes. this is a scam',
  5000: 'half way there version 2.0',
  10000: 'try doing something else. like breathing',
  15000: 'im starting to think that your becoming insane',
  20000: '....20k how wow.... you need to get out of here',
  30000: 'bro 30k is okay but you need to stop',
  40000: 'you should stop here. but you wont',
  50000: '50k!! holy you should touch grass',
  75000: 'i said touch grass not your screen',
  100000: 'at this point you should be in a mental hospital',
  250000: 'click more i dare you',
  500000: 'half a mill.. you just wish this was money',
  1000000: 'WOW thats like a lottory win. but its not money',
  5000000: 'im still not giving you anything',
  10000000: 'you should get a job. this is not a hobby',
  25000000: '25 million and the button is now afraid that your hurting him',
  50000000: 'button is now hurting and thinking it will file a case on you',
  100000000: 'you are now in court with the button. he is suing you for hurting him',
  250000000: '250 million. the button is now in the hospital. you should be too',
  500000000: '500 million. the button is now dead and you still want to click it',
  1000000000: '1 billion you know your closer to your goal now',
  2500000000: '2.5 billion alright....... a few more billion',
  5000000000: '5 billion. half way there 3.0',
  10000000000: 'you are now the concept of boredom. GET A LIFE',
};

const RANK_TIERS = [
  'Bronze I', 'Bronze II', 'Bronze III', 'Bronze IV', 'Bronze V',
  'Silver I', 'Silver II', 'Silver III', 'Silver IV', 'Silver V',
  'Gold I', 'Gold II', 'Gold III', 'Gold IV', 'Gold V',
  'Platinum I', 'Platinum II', 'Platinum III', 'Platinum IV', 'Platinum V',
  'Diamond I', 'Diamond II', 'Diamond III', 'Diamond IV', 'Diamond V',
  'Obsidian I', 'Obsidian II', 'Obsidian III', 'Obsidian IV', 'Obsidian V',
];

const RANK_THRESHOLDS = [
  0, 1000, 5000, 15000, 40000,
  100000, 250000, 500000, 1000000, 2000000,
  4000000, 7000000, 11000000, 16000000, 22000000,
  30000000, 40000000, 52000000, 66000000, 82000000,
  100000000, 110000000, 120000000, 130000000, 140000000,
  143000000, 146000000, 148000000, 149000000, 150000000,
];

const SERVER_PARTS = {
  CPU: [
    { name: 'Pentium G6400', cost: 350, power: 30, socket: 'LGA1200', tdp: 65 },
    { name: 'Core i3-12100F', cost: 950, power: 70, socket: 'LGA1700', tdp: 60 },
    { name: 'Core i5-12400F', cost: 1800, power: 120, socket: 'LGA1700', tdp: 65 },
    { name: 'Core i5-12600K', cost: 2600, power: 180, socket: 'LGA1700', tdp: 125 },
    { name: 'Ryzen 5 5600', cost: 1600, power: 90, socket: 'AM4', tdp: 65 },
    { name: 'Ryzen 5 7600X', cost: 2850, power: 170, socket: 'AM5', tdp: 105 },
    { name: 'Ryzen 7 5700X', cost: 2800, power: 165, socket: 'AM4', tdp: 65 },
    { name: 'Ryzen 7 7700X', cost: 4200, power: 240, socket: 'AM5', tdp: 105 },
    { name: 'Core i7-12700K', cost: 3500, power: 220, socket: 'LGA1700', tdp: 125 },
    { name: 'Core i7-13700K', cost: 5200, power: 300, socket: 'LGA1700', tdp: 125 },
    { name: 'Ryzen 9 5900X', cost: 5000, power: 270, socket: 'AM4', tdp: 105 },
    { name: 'Ryzen 9 7900X', cost: 6800, power: 360, socket: 'AM5', tdp: 170 },
    { name: 'Core i9-12900K', cost: 6200, power: 340, socket: 'LGA1700', tdp: 241 },
    { name: 'Core i9-13900K', cost: 9800, power: 520, socket: 'LGA1700', tdp: 253 },
    { name: 'Ryzen 9 7950X', cost: 10000, power: 510, socket: 'AM5', tdp: 170 },
    { name: 'Ryzen 9 9950X', cost: 14000, power: 650, socket: 'AM5', tdp: 170 },
  ],
  Motherboard: [
    { name: 'H610', cost: 500, power: 18, socket: 'LGA1700', memory_generation: 'DDR4', form_factor: 'Micro-ATX' },
    { name: 'B560', cost: 550, power: 20, socket: 'LGA1200', memory_generation: 'DDR4', form_factor: 'ATX' },
    { name: 'B660', cost: 700, power: 30, socket: 'LGA1700', memory_generation: 'DDR4', form_factor: 'ATX' },
    { name: 'Z790', cost: 1500, power: 60, socket: 'LGA1700', memory_generation: 'DDR5', form_factor: 'ATX' },
    { name: 'B550', cost: 600, power: 25, socket: 'AM4', memory_generation: 'DDR4', form_factor: 'ATX' },
    { name: 'X570', cost: 1200, power: 45, socket: 'AM4', memory_generation: 'DDR4', form_factor: 'ATX' },
    { name: 'B650', cost: 900, power: 40, socket: 'AM5', memory_generation: 'DDR5', form_factor: 'ATX' },
    { name: 'X670', cost: 1800, power: 80, socket: 'AM5', memory_generation: 'DDR5', form_factor: 'ATX' },
  ],
  RAM: [
    { name: '16GB DDR4-3200', cost: 200, power: 25, generation: 'DDR4', capacity: 16, speed: 3200 },
    { name: '32GB DDR4-3600', cost: 400, power: 45, generation: 'DDR4', capacity: 32, speed: 3600 },
    { name: '32GB DDR4-4800', cost: 550, power: 60, generation: 'DDR4', capacity: 32, speed: 4800 },
    { name: '32GB DDR5-6000', cost: 700, power: 70, generation: 'DDR5', capacity: 32, speed: 6000 },
    { name: '64GB DDR5-6000', cost: 1500, power: 120, generation: 'DDR5', capacity: 64, speed: 6000 },
    { name: '64GB DDR5-6400', cost: 1900, power: 150, generation: 'DDR5', capacity: 64, speed: 6400 },
  ],
  GPU: [
    { name: 'GTX 1650 Super', cost: 1400, power: 110, vram: 4, length: 180, power_draw: 100 },
    { name: 'GTX 1660 Super', cost: 1700, power: 140, vram: 6, length: 200, power_draw: 125 },
    { name: 'GTX 1660 Ti', cost: 1900, power: 155, vram: 6, length: 200, power_draw: 130 },
    { name: 'RTX 2060 6GB', cost: 2100, power: 180, vram: 6, length: 205, power_draw: 160 },
    { name: 'RTX 3060 12GB', cost: 2200, power: 200, vram: 12, length: 210, power_draw: 170 },
    { name: 'RTX 3060 Ti 8GB', cost: 2600, power: 230, vram: 8, length: 215, power_draw: 200 },
    { name: 'RX 6700 XT 12GB', cost: 2700, power: 220, vram: 12, length: 220, power_draw: 230 },
    { name: 'RTX 3070 8GB', cost: 3200, power: 260, vram: 8, length: 230, power_draw: 220 },
    { name: 'RTX 3070 Ti 8GB', cost: 3600, power: 290, vram: 8, length: 232, power_draw: 240 },
    { name: 'RTX 4070 12GB', cost: 5400, power: 390, vram: 12, length: 240, power_draw: 200 },
    { name: 'RTX 4070 Super 12GB', cost: 6200, power: 430, vram: 12, length: 245, power_draw: 220 },
    { name: 'RX 7800 XT 16GB', cost: 5500, power: 430, vram: 16, length: 245, power_draw: 263 },
    { name: 'RTX 4080 16GB', cost: 8500, power: 590, vram: 16, length: 255, power_draw: 320 },
    { name: 'RTX 4090 24GB', cost: 12000, power: 760, vram: 24, length: 268, power_draw: 450 },
    { name: 'RX 7900 XT 20GB', cost: 9800, power: 680, vram: 20, length: 267, power_draw: 315 },
    { name: 'RX 7900 XTX 24GB', cost: 11000, power: 720, vram: 24, length: 270, power_draw: 355 },
  ],
  PSU: [
    { name: '550W Bronze', cost: 200, power: 20, watts: 550 },
    { name: '650W Gold', cost: 360, power: 35, watts: 650 },
    { name: '750W Gold', cost: 550, power: 55, watts: 750 },
    { name: '850W Gold', cost: 800, power: 75, watts: 850 },
    { name: '1000W Platinum', cost: 1100, power: 90, watts: 1000 },
    { name: '1200W Titanium', cost: 1500, power: 110, watts: 1200 },
    { name: '1500W Titanium', cost: 2100, power: 140, watts: 1500 },
  ],
  Case: [
    { name: 'Mini-ITX Case', cost: 220, power: 15, supports: ['Mini-ITX'], gpu_max_length: 180, psu_max_length: 140 },
    { name: 'Micro-ATX Case', cost: 250, power: 20, supports: ['Micro-ATX', 'Mini-ITX'], gpu_max_length: 220, psu_max_length: 170 },
    { name: 'ATX Case', cost: 450, power: 40, supports: ['ATX', 'Micro-ATX', 'Mini-ITX'], gpu_max_length: 330, psu_max_length: 190 },
    { name: 'E-ATX Tower', cost: 700, power: 65, supports: ['ATX', 'Micro-ATX', 'Mini-ITX'], gpu_max_length: 380, psu_max_length: 220 },
    { name: 'Workstation Case', cost: 950, power: 90, supports: ['ATX', 'Micro-ATX', 'Mini-ITX'], gpu_max_length: 420, psu_max_length: 240 },
  ],
};

const SERVER_CATEGORIES = ['CPU', 'Motherboard', 'RAM', 'GPU', 'PSU', 'Case'];

// x/y position (percent of tree box) for each non-motherboard slot, matching
// the original pos_hint layout around the central motherboard node.
const TREE_POSITIONS = {
  CPU: { x: 0.5, y: 0.14 },
  RAM: { x: 0.16, y: 0.5 },
  GPU: { x: 0.84, y: 0.5 },
  PSU: { x: 0.28, y: 0.86 },
  Case: { x: 0.72, y: 0.86 },
};
