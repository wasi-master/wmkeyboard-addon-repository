#!/usr/bin/env python3
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_FILE = ROOT / "dictionaries" / "en-medical.txt"

# Define frequency tier dictionary mapping terms to frequency values
# Tier 1 (980-950): Ultra-common medical words & basic clinical terms
t1_terms = [
    "aspirin", "ibuprofen", "acetaminophen", "tylenol", "advil", "doctor", "patient",
    "hospital", "clinic", "medicine", "medical", "pharmacy", "pharmacist", "dose",
    "dosage", "prescription", "pill", "tablet", "capsule", "syrup", "injection",
    "vaccine", "virus", "bacteria", "bacterial", "viral", "fungal", "infection",
    "infectious", "allergy", "allergic", "asthma", "diabetes", "diabetic", "stroke",
    "seizure", "cancer", "tumor", "biopsy", "blood", "plasma", "pulse", "oxygen",
    "x-ray", "mri", "ct", "scan", "ultrasound", "iv", "drip", "syringe", "needle",
    "bandage", "wound", "suture", "stitches", "fracture", "sprain", "edema", "fever",
    "nausea", "vomiting", "fatigue", "pain", "tremor", "spasm", "reflex", "lesion",
    "benign", "malignant", "acute", "chronic", "diagnostic", "therapy", "therapeutic",
    "antibiotic", "antiviral", "antifungal", "insulin", "statin", "steroid", "inhaler",
    "stethoscope", "otoscope", "catheter", "scalpel", "forceps", "heart", "lung",
    "liver", "kidney", "brain", "stomach", "colon", "artery", "vein", "nerve", "muscle",
    "bone", "joint", "tissue", "cell", "cellular", "gene", "genetic", "dna", "rna",
    "protein", "enzyme", "hormone", "antibody", "antigen", "immune", "immunity"
]

# Tier 2 (940-900): Common prescription drugs, generic compounds, major conditions & procedures
t2_terms = [
    "amoxicillin", "metformin", "atorvastatin", "lisinopril", "levothyroxine", "omeprazole",
    "gabapentin", "hydrochlorothiazide", "sertraline", "escitalopram", "prednisone", "albuterol",
    "amlodipine", "metoprolol", "losartan", "simvastatin", "duloxetine", "alprazolam",
    "lorazepam", "zolpidem", "ondansetron", "naproxen", "celecoxib", "tramadol",
    "oxycodone", "hydrocodone", "fentanyl", "morphine", "methadone", "buprenorphine",
    "naloxone", "propofol", "ketamine", "lidocaine", "bupivacaine", "penicillin",
    "cephalexin", "azithromycin", "ciprofloxacin", "doxycycline", "metronidazole",
    "fluconazole", "acyclovir", "valacyclovir", "heparin", "warfarin", "clopidogrel",
    "furosemide", "spironolactone", "dexamethasone", "methylprednisolone", "triamcinolone",
    "fluticasone", "montelukast", "famotidine", "ranitidine", "pantoprazole", "loperamide",
    "docusate", "senna", "bisacodyl", "polyethylene", "glycol", "diphenhydramine",
    "loratadine", "cetirizine", "fexofenadine", "pseudoephedrine", "phenylephrine",
    "dextromethorphan", "guaifenesin", "chlorpheniramine", "hydroxyzine", "promethazine",
    "proctitis", "gastritis", "appendectomy", "cholecystectomy", "mastectomy", "hysterectomy",
    "prostatectomy", "colonoscopy", "endoscopy", "bronchoscopy", "dialysis", "angioplasty",
    "pacemaker", "intubation", "tracheostomy", "defibrillator", "echocardiogram",
    "electrocardiogram", "ecg", "ekg", "hypertension", "hypotension", "arrhythmia",
    "tachycardia", "bradycardia", "pneumonia", "bronchitis", "copd", "emphysema",
    "gastroenteritis", "hepatitis", "cirrhosis", "pancreatitis", "nephritis", "pyelonephritis",
    "cystitis", "prostatitis", "endometriosis", "fibroids", "psoriasis", "eczema",
    "dermatitis", "urticaria", "alopecia", "melanoma", "carcinoma", "sarcoma",
    "lymphoma", "leukemia", "myeloma", "glioblastoma", "alzheimers", "parkinsons",
    "huntingtons", "amyotrophic", "sclerosis", "lupus", "rheumatoid", "osteoarthritis",
    "gout", "osteoporosis", "anemia", "thrombosis", "embolism", "aneurysm", "ischemia",
    "infarction", "angina", "atherosclerosis", "hyperlipidemia", "hypoglycemia", "ketoacidosis"
]

# Tier 3 (890-800): Specialized pharmacology, biopharmaceuticals, monoclonal antibodies, surgery & devices
t3_terms = [
    "pembrolizumab", "nivolumab", "rituximab", "trastuzumab", "adalimumab", "infliximab",
    "etanercept", "dupilumab", "ustekinumab", "secukinumab", "vedolizumab", "empagliflozin",
    "dapagliflozin", "tirzepatide", "semaglutide", "dulaglutide", "apixaban", "rivaroxaban",
    "dabigatran", "ticagrelor", "prasugrel", "alteplase", "tenecteplase", "vancomycin",
    "daptomycin", "meropenem", "piperacillin", "tazobactam", "ceftriaxone", "cefepime",
    "levofloxacin", "amphotericin", "voriconazole", "caspofungin", "remdesivir", "nirmatrelvir",
    "ritonavir", "tenofovir", "emtricitabine", "dolutegravir", "bictegravir", "oseltamivir",
    "motrin", "aleve", "lipitor", "crestor", "zocor", "nexium", "prilosec", "protonix",
    "synthroid", "ventolin", "proair", "symbicort", "advair", "breo", "trelegy",
    "spiriva", "xolair", "fasenra", "humira", "enbrel", "remicade", "stelara",
    "cosentyx", "taltz", "skyrizi", "tremfya", "entyvio", "rinvoq", "xeljanz",
    "eliquis", "xarelto", "pradaxa", "plavix", "brilinta", "coumadin", "lovenox",
    "januvia", "jardiance", "farxiga", "victoza", "trulicity", "ozempic", "rybelsus",
    "wegovy", "mounjaro", "zepbound", "biktarvy", "triumeq", "paxlovid", "veklury",
    "keytruda", "opdivo", "tecentriq", "imfinzi", "yervoy", "avastin", "herceptin",
    "rituxan", "darzalex", "revlimid", "imbruvica", "venclexta", "jakafi", "vyvanse",
    "adderall", "concerta", "ritalin", "prozac", "zoloft", "paxil", "lexapro",
    "effexor", "cymbalta", "wellbutrin", "haldol", "risperdal", "zyprexa", "seroquel",
    "abilify", "clozaril", "depakote", "tegretol", "lamictal", "keppra", "topamax",
    "neurontin", "lyrica", "xanax", "valium", "ativan", "klonopin", "ambien",
    "suboxone", "zofran", "imodium", "claritin", "zyrtec", "allegra", "flonase",
    "pericardiocentesis", "thoracentesis", "paracentesis", "arthrocentesis", "endarterectomy",
    "craniotomy", "laminectomy", "discectomy", "arthroplasty", "fundoplication", "myotomy",
    "trabeculectomy", "vitrectomy", "blepharoplasty", "rhinoplasty", "tympanoplasty",
    "electrocautery", "capnograph", "sphygmomanometer", "laparoscope", "laryngoscope",
    "speculum", "rongeur", "curette", "microvascular", "endovascular", "fluoroscopy",
    "dermatoscope", "phoropter", "funduscope", "nephrectomy", "splenectomy", "gastrectomy",
    "esophagectomy", "lobectomy", "pneumonectomy", "osteotomy", "gastrostomy", "jejunostomy",
    "ileostomy", "colostomy", "cystostomy", "thoracostomy", "amniocentesis", "cystoscopy",
    "laparoscopy", "arthroscopy", "mediastinoscopy", "gastroscopy", "sigmoidoscopy",
    "colposcopy", "hysteroscopy", "valvuloplasty", "cardioversion", "plasmapheresis",
    "leukapheresis", "radiotherapy", "chemotherapy", "immunotherapy", "cryoablation",
    "chemoembolization", "vertebroplasty", "kyphoplasty", "abdominoplasty", "liposuction",
    "myringotomy", "tonsillectomy", "adenoidectomy", "thyroidectomy", "parathyroidectomy",
    "adrenalectomy", "thrombectomy", "embolectomy", "vitrectomy", "trabeculoplasty"
]

# Tier 4 (790-700): Obscure chemical compound names, rare diseases, syndromes, complex jargon
t4_terms = [
    "acetylsalicylic", "pseudoephedrine", "chlorpheniramine", "hydromorphone", "oxymorphone",
    "suxamethonium", "rocuronium", "cisatracurium", "sugammadex", "neostigmine", "pyridostigmine",
    "glycopyrrolate", "scopolamine", "dobutamine", "norepinephrine", "epinephrine", "vasopressin",
    "milrinone", "nitroprusside", "nitroglycerin", "isosorbide", "hydralazine", "minoxidil",
    "eplerenone", "acetazolamide", "bumetanide", "torsemide", "chlorthalidone", "indapamide",
    "triamterene", "amiloride", "sarcoidosis", "amyloidosis", "hemochromatosis", "porphyria",
    "myasthenia", "scleroderma", "dermatomyositis", "polymyositis", "ankylosing", "spondylitis",
    "fibromyalgia", "polymyalgia", "vasculitis", "granulomatosis", "polyarteritis", "thromboangiitis",
    "erythromelalgia", "raynaud", "sjogren", "behcet", "takayasu", "kawasaki", "churg-strauss",
    "wegener", "goodpasture", "alport", "fanconi", "gaucher", "fabry", "niemann-pick",
    "tay-sachs", "krabbe", "pompe", "forbes", "mcardle", "hurler", "hunter", "sanfilippo",
    "morquio", "maroteaux-lamy", "sly", "zellweger", "refsum", "achondroplasia", "neurofibromatosis",
    "tuberous", "li-fraumeni", "lynch", "gardner", "turcot", "peutz-jeghers", "cowden",
    "gorlin", "sturge-weber", "klippel-trenaunay", "osler-weber-rendu", "ataxia-telangiectasia",
    "bloom", "rothmund-thomson", "werner", "cockayne", "xeroderma", "dyskeratosis",
    "epidermolysis", "pemphigus", "pemphigoid", "hidradenitis", "rosacea", "melasma",
    "keloid", "astrocytoma", "oligodendroglioma", "ependymoma", "medulloblastoma", "meningioma",
    "schwannoma", "neuroblastoma", "retinoblastoma", "nephroblastoma", "hepatoblastoma",
    "rhabdomyosarcoma", "leiomyosarcoma", "osteosarcoma", "chondrosarcoma", "ewing", "kaposi",
    "merkel", "chordoma", "craniopharyngioma", "pheochromocytoma", "paraganglioma", "insulinoma",
    "glucagonoma", "gastrinoma", "vipoma", "somatostatinoma", "carcinoid", "leishmaniasis",
    "schistosomiasis", "filariasis", "trypanosomiasis", "cysticercosis", "echinococcosis",
    "toxoplasmosis", "histoplasmosis", "coccidioidomycosis", "blastomycosis", "aspergillosis",
    "candidiasis", "mucormycosis", "cryptococcosis", "actinomycosis", "nocardiosis", "leprosy",
    "diphtheria", "pertussis", "tetanus", "cholera", "typhoid", "brucellosis", "tularemia",
    "glanders", "melioidosis", "psittacosis", "lyme", "leptospirosis", "syphilis", "gonorrhea",
    "chlamydia", "trichomoniasis", "scabies", "pediculosis", "rabies", "measles", "mumps",
    "rubella", "varicella", "zoster", "influenza", "dengue", "chikungunya", "zika", "ebola",
    "marburg", "lassa", "hantavirus", "mpox", "poliomyelitis", "kuru", "creutzfeldt-jakob",
    "wilson", "marfan", "ehlers-danlos", "pancoast", "horner", "guillain-barre", "charcot-marie-tooth",
    "brown-sequard", "wallenberg", "wernicke", "korsakoff", "korsakoffs", "buerger", "henoch-schonlein"
]

# Tier 5 (690-400): Utterly obscure terms, rare medical phenomena, ultra-rare syndromes, niche chemical compounds & tools
t5_terms = [
    "acanthosis", "actinomycoma", "adamantinoma", "aglossia", "ainhum", "alkaptonuria",
    "amelogenesis", "ankyloblepharon", "astereognosis", "autoerythrocyte", "batrachoplasty",
    "borborygmus", "caput-medusae", "chalazion", "cherubism", "dacryocystorhinostomy",
    "dysdiadochokinesia", "elephantiasis", "encephalocraniocutaneous", "erythroderma",
    "fabella", "formication", "gastroschisis", "halitosis", "hematidrosis", "hemiballismus",
    "hidradenoma", "hypertrichosis", "ichthyosis", "keratoacanthoma", "lymphedema",
    "meconium", "mydriasis", "nystagmus", "odontoma", "opisthotonos", "pachydermoperiostosis",
    "palilalia", "paraphimosis", "phocomelia", "pica", "pilomatricoma", "priapism",
    "prosopagnosia", "pruritus", "rhinophyma", "sialolithiasis", "steatopygia", "syringomyelia",
    "tenosynovitis", "trichotillomania", "trismus", "tyrosinemia", "xanthoma", "xerostomia",
    "zolgensma", "luxturna", "spinraza", "trogarzo", "pyrukynd", "relyvrio", "daybue",
    "veozah", "fabhalta", "filspari", "elrexfio", "talvey", "epkinly", "rystiggo", "columvi",
    "miconazole", "ketoconazole", "itraconazole", "posaconazole", "isavuconazole", "micafungin",
    "anidulafungin", "terbinafine", "griseofulvin", "flucytosine", "nystatin", "chlorhexidine",
    "hexachlorophene", "benzalkonium", "povidone-iodine", "bacitracin", "polymyxin",
    "neomycin", "mupirocin", "retapamulin", "lefamulin", "fidaxomicin", "rifaximin",
    "nitazoxanide", "ivermectin", "praziquantel", "albendazole", "mebendazole", "permethrin",
    "malathion", "spinosad", "lindane", "crotamiton", "eflornithine", "trioxsalen",
    "methoxsalen", "anthralin", "calcipotriene", "acitretin", "isotretinoin", "tretinoin",
    "tazarotene", "adapalene", "trifarotene", "fluorouracil", "imiquimod", "ingenol",
    "tirbanibulin", "cobimetinib", "trametinib", "binimetinib", "selumetinib", "dabrafenib",
    "vemurafenib", "encorafenib", "gefitinib", "erlotinib", "afatinib", "osimertinib",
    "dacomitinib", "crizotinib", "ceritinib", "alectinib", "brigatinib", "lorlatinib",
    "cabozantinib", "vandetanib", "axitinib", "lenvatinib", "pazopanib", "regorafenib",
    "sorafenib", "sunitinib", "tivozanib", "fruquintinib", "ibrutinib", "acalabrutinib",
    "zanubrutinib", "pirtobrutinib", "idelalisib", "duvelisib", "copanlisib", "umbralisib",
    "venetoclax", "ruxolitinib", "fedratinib", "pacritinib", "momelotinib", "tofacitinib",
    "baricitinib", "upadacitinib", "filgotinib", "abrocitinib", "deucravacitinib", "avapritinib",
    "ripretinib", "pemigatinib", "infigratinib", "futibatinib", "capmatinib", "tepotinib",
    "selpercatinib", "pralsetinib", "sotorasib", "adagrasib", "tucatinib", "neratinib",
    "lapatinib", "palbociclib", "ribociclib", "abemaciclib", "elacestrant", "fulvestrant",
    "tamoxifen", "toremifene", "raloxifene", "letrozole", "anastrozole", "exemestane",
    "degarelix", "relugolix", "leuprolide", "goserelin", "triptorelin", "histrelin",
    "bicalutamide", "enzalutamide", "apalutamide", "darolutamide", "abiraterone",
    "aminoglutethimide", "trilostane", "mitotane", "anhedonia", "abulia", "akathisia",
    "asterixis", "ageusia", "anosmia", "dysgeusia", "parosmia", "allodynia", "hyperalgesia",
    "dysesthesia", "paresthesia", "synesthesia", "chorea", "athetosis", "ballismus",
    "dystonia", "myoclonus", "ataxia", "dysmetria", "dysarthria", "dysphagia", "dysphasia",
    "aphasia", "apraxia", "agnosia", "alexia", "agraphia", "acrodermatitis", "actinic",
    "keratosis", "amyloid", "ankylosis", "anthracosis", "asbestosis", "byssinosis",
    "silicosis", "siderosis", "calcinosis", "catecholamine", "cholestasis", "chondrocalcinosis",
    "chorioamnionitis", "coprolalia", "copropraxia", "cryptorchidism", "dacryocystitis",
    "decubitus", "diaphoresis", "dyssynergia", "dysuria", "encopresis", "enuresis",
    "epistaxis", "exophthalmos", "galactorrhea", "gynecomastia", "hematemesis", "hematochezia",
    "hematuria", "hemoptysis", "hepatomegaly", "splenomegaly", "hepatosplenomegaly",
    "hydrocephalus", "hydronephrosis", "hyperacusis", "hyperhidrosis", "hyperkeratosis",
    "hyperosmia", "hyposmia", "hysterosalpingography", "icterus", "jaundice", "keratomalacia",
    "leiomyoma", "lipoma", "lymphadenopathy", "macroglossia", "microglossia", "micrognathia",
    "macrognathia", "microcephaly", "macrocephaly", "miosis", "nyctalopia", "odynophagia",
    "oliguria", "anuria", "polyuria", "polydipsia", "polyphagia", "onycholysis",
    "onychomycosis", "paronychia", "orthopnea", "trepopnea", "platypnea", "otorrhagia",
    "otorrhea", "papilledema", "petechiae", "purpura", "ecchymosis", "phlebotomy",
    "pneumaturia", "pneumoperitoneum", "pneumomediastinum", "poikilothermia", "polydactyly",
    "syndactyly", "oligodactyly", "proptosis", "ptosis", "pyuria", "rhinorrhea", "sialorrhea",
    "steatorrhea", "stridor", "tenesmus", "tinnitus", "tympanometry", "volvulus",
    "intussusception", "xanthelasma", "xerophthalmia", "yansian", "zuckerkandl",
    "kirschner", "steinmann", "yankauer", "bovie", "cusa", "ecmo", "iabp", "lvad",
    "bipap", "cpap", "hemovac", "pachymeter", "keratometer", "retinoscope", "slap-lesion",
    "bankart", "hill-sachs", "lisfranc", "chopart", "colles", "smiths", "bennett",
    "rolando", "boxer", "monterggia", "galeazzi", "salter-harris", "panner", "sever",
    "freiberg", "kohler", "kienbock", "legg-calve-perthes", "osgood-schlatter", "scheuermann"
]

def build():
    words = {}

    def add_tier(terms, start_freq, step):
        freq = start_freq
        for t in terms:
            t_clean = t.strip().lower()
            if not t_clean:
                continue
            if t_clean not in words:
                words[t_clean] = freq
                freq = max(400, freq - step)

    add_tier(t1_terms, 980, 2)
    add_tier(t2_terms, 940, 2)
    add_tier(t3_terms, 890, 2)
    add_tier(t4_terms, 790, 2)
    add_tier(t5_terms, 690, 1)

    sorted_words = sorted(words.items(), key=lambda x: (-x[1], x[0]))

    lines = [
        "# Exhaustive Medical & Clinical Dictionary for WM Keyboard (langId=en)",
        "# Comprehensive coverage of chemical compound names, generic & brand pharmaceuticals, common & rare diseases, surgical procedures, diagnostic equipment, and medical terminology.",
    ]

    for word, freq in sorted_words:
        lines.append(f"{word} {freq}")

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Successfully generated {OUTPUT_FILE} with {len(sorted_words)} terms.")

if __name__ == "__main__":
    build()
