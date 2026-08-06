#!/usr/bin/env python3
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_FILE = ROOT / "dictionaries" / "en-legal.txt"

# Tier 1 (980-950): Ultra-common legal terms, core legal vocabulary, top Latin maxims
t1_terms = [
    "lawyer", "attorney", "counsel", "judge", "court", "courtroom", "juror", "jury",
    "verdict", "trial", "lawsuit", "litigation", "litigant", "plaintiff", "defendant",
    "prosecutor", "prosecution", "defense", "advocate", "jurisdiction", "statute",
    "statutory", "constitutional", "constitution", "amendment", "clause", "contract",
    "agreement", "breach", "liability", "liable", "tort", "negligence", "damages",
    "remedy", "injunction", "subpoena", "warrant", "affidavit", "testimony", "witness",
    "deposition", "evidence", "proof", "exhibit", "objection", "sustained", "overruled",
    "appeal", "appellant", "appellee", "appellate", "supreme", "tribunal", "docket",
    "bail", "custody", "parole", "probation", "sentence", "conviction", "acquittal",
    "felony", "misdemeanor", "crime", "criminal", "civil", "jurisprudence", "legal",
    "legality", "illegal", "lawful", "unlawful", "justice", "judicial", "judiciary",
    "habeas", "corpus", "pro", "bono", "bona", "fide", "mens", "rea", "actus", "reus",
    "stare", "decisis", "prima", "facie", "sub", "poena", "voir", "dire", "certiorari",
    "mandamus", "res", "judicata", "ex", "parte", "inter", "alia", "per", "curiam",
    "de", "facto", "de", "jure", "in", "loco", "parentis", "caveat", "emptor", "nolo",
    "contendere", "alibi", "duress", "indictment", "arraignment", "plea", "settlement"
]

# Tier 2 (940-900): Common contracts, civil procedure, property, family, torts, constitutional terms
t2_terms = [
    "indemnification", "indemnity", "indemnify", "warranty", "guarantee", "covenant",
    "arbitration", "arbitrator", "mediation", "mediator", "adjudication", "adjudicator",
    "estoppel", "promissory", "consideration", "rescission", "restitution", "renunciation",
    "repudiation", "liquidated", "quantum", "meruit", "unjust", "enrichment", "novation",
    "assignment", "assignee", "assignor", "delegation", "severability", "counterpart",
    "confidentiality", "non-disclosure", "disclaimer", "limitation", "force", "majeure",
    "easement", "tenancy", "tenant", "landlord", "lease", "leasehold", "freehold",
    "conveyance", "deed", "mortgage", "foreclosure", "lien", "encumbrance", "title",
    "chattel", "fixture", "forensic", "probate", "testator", "testatrix", "executor",
    "executrix", "beneficiary", "bequest", "devise", "intestate", "intestacy", "codicil",
    "fiduciary", "trustee", "trustor", "custodian", "guardian", "conservator", "power",
    "ward", "guardianship", "adoption", "custody", "alimony", "divorce", "annulment",
    "matrimonial", "paternity", "maintenance", "garnishment", "repossess", "insolvency",
    "bankrupt", "bankruptcy", "liquidation", "receivership", "reorganization", "creditor",
    "debtor", "default", "collateral", "guarantor", "promissory", "note", "debenture",
    "overrule", "remand", "affirm", "vacate", "dismiss", "dismissal", "summary",
    "judgment", "pleading", "complaint", "summons", "answer", "counterclaim", "cross-claim",
    "joinder", "interpleader", "class", "action", "standing", "mootness", "ripeness",
    "venue", "forum", "conveniens", "discovery", "interrogatory", "impeachment", "hearsay",
    "privilege", "relevance", "admissible", "inadmissible", "subpoena", "duces", "tecum",
    "deposition", "transcription", "stenographer", "cross-examination", "direct-examination",
    "rebuttal", "surrebuttal", "mistrial", "peremptory", "challenge", "venire", "sequestration"
]

# Tier 3 (890-800): Corporate law, IP, criminal procedure, tax, administrative, international, regulatory
t3_terms = [
    "corporation", "corporate", "incorporation", "shareholder", "stockholder", "bylaws",
    "director", "officer", "resolution", "dividend", "merger", "acquisition", "dissolution",
    "derivative", "prospectus", "securities", "insider", "compliance", "governance",
    "antitrust", "monopoly", "cartel", "monopsony", "trademark", "patent", "copyright",
    "infringement", "royalties", "license", "licensor", "licensee", "plagiarism", "trade",
    "secret", "misappropriation", "fair", "use", "prior", "art", "novelty", "non-obviousness",
    "extradition", "asylum", "deportation", "expatriation", "sovereign", "immunity",
    "treaty", "convention", "protocol", "ratification", "sanction", "embargo", "jurisdiction",
    "extraterritorial", "naturalization", "visas", "citizenship", "alien", "denaturalization",
    "homicide", "manslaughter", "murder", "assault", "battery", "arson", "burglary",
    "larceny", "robbery", "embezzlement", "extortion", "blackmail", "bribery", "perjury",
    "forgery", "fraud", "fraudulent", "racketeering", "conspiracy", "solicitation", "attempt",
    "accomplice", "accessory", "abettor", "malice", "aforethought", "premeditation", "intent",
    "recklessness", "mens", "culpability", "exculpatory", "inculpatory", "mitigating",
    "aggravating", "recidivism", "recidivist", "expungement", "clemency", "pardon", "commutation",
    "restitution", "rehabilitation", "incarceration", "imprisonment", "detention", "correctional",
    "interstate", "commerce", "preemption", "equal", "protection", "due", "process",
    "substantive", "procedural", "eminent", "domain", "condemnation", "expropriation", "taking",
    "police", "power", "commerce", "dormant", "federalism", "delegation", "doctrine",
    "administrative", "rulemaking", "adjudication", "agency", "regulation", "regulatory",
    "promulgation", "sunset", "clause", "enabling", "act", "deference", "chevron", "skidmore",
    "claim", "specification", "enablement", "utility", "obviousness", "patentability",
    "provisional", "reissue", "reexamination", "inter", "partes", "post", "grant", "review",
    "grantor", "settlor", "corpus", "reversionary", "capital", "gains", "deduction", "exemption",
    "taxable", "audit", "assessment", "evasion", "avoidance", "taxation", "withholding"
]

# Tier 4 (790-700): Obscure Latin maxims, technical legal Latin, property/torts/procedure terms, specialized jargon
t4_terms = [
    "ab", "initio", "ad", "hoc", "ad", "litem", "ad", "valorem", "amiscus", "curiae",
    "argumentum", "a", "fortiori", "bona", "vacantia", "casu", "fortuito", "caveat",
    "corpus", "cum", "causa", "damnum", "absque", "injuria", "de", "bonis", "asportatis",
    "de", "novo", "dictum", "obiter", "ejusdem", "generis", "expressio", "unius", "est",
    "exclusio", "alterius", "ex", "post", "facto", "in", "absentia", "in", "camera",
    "in", "forma", "pauperis", "in", "personam", "in", "rem", "inter", "vivos", "ipso",
    "facto", "lex", "loci", "lex", "fori", "lis", "pendens", "locus", "standi", "malum",
    "in", "se", "malum", "prohibitum", "modus", "operandi", "mutatis", "mutandis", "ne",
    "bis", "in", "idem", "nisi", "prius", "nolle", "prosequi", "non", "compos", "mentis",
    "non", "sequitur", "nunc", "pro", "tunc", "pari", "passu", "pendente", "lite", "per",
    "se", "post", "mortem", "pro", "forma", "pro", "rata", "pro", "tanto", "quid",
    "pro", "quo", "ratio", "decidendi", "re", "respondeat", "superior", "sine", "qua",
    "non", "sub", "judice", "sua", "sponte", "substantia", "uberrimae", "fidei", "ultra",
    "vires", "volenti", "non", "fit", "injuria", "scintilla", "certifiable", "hereditament",
    "seisin", "feoffment", "subinfeudation", "fee", "simple", "fee", "tail", "remainder",
    "reversion", "executory", "interest", "usufruct", "hypothecation", "chose", "in",
    "action", "bailment", "bailor", "bailee", "pawnor", "pawnee", "usury", "usurious",
    "champerty", "maintenance", "barretry", "tortious", "conversion", "trespass", "nuisance",
    "defamation", "slander", "libel", "scandalum", "magnatum", "scienter", "strict",
    "vicarious", "joint", "several", "contribution", "subrogation", "marshaling", "attornment",
    "in", "limine", "de", "bene", "esse", "ex", "officio", "per", "capita", "per", "stirpes",
    "res", "gestae", "caveat", "actor", "noscitur", "a", "sociis", "ejusdem", "generis",
    "flotsam", "jetsam", "salvage", "demurrage", "charterparty", "maritime", "seaworthiness",
    "jettison", "freight", "bottomry", "respondentia", "general", "average", "p&i"
]

def generate_dictionary():
    terms_map = {}
    
    # Process Tier 1 (980 -> 950)
    score = 980
    for term in t1_terms:
        term = term.strip().lower()
        if term and term not in terms_map:
            terms_map[term] = score
            score = max(score - 2, 950)
            
    # Process Tier 2 (940 -> 900)
    score = 940
    for term in t2_terms:
        term = term.strip().lower()
        if term and term not in terms_map:
            terms_map[term] = score
            score = max(score - 1, 900)
            
    # Process Tier 3 (890 -> 800)
    score = 890
    for term in t3_terms:
        term = term.strip().lower()
        if term and term not in terms_map:
            terms_map[term] = score
            score = max(score - 1, 800)
            
    # Process Tier 4 (790 -> 700)
    score = 790
    for term in t4_terms:
        term = term.strip().lower()
        if term and term not in terms_map:
            terms_map[term] = score
            score = max(score - 1, 700)
            
    # Sort descending by score, then alphabetically by term
    sorted_terms = sorted(terms_map.items(), key=lambda x: (-x[1], x[0]))
    
    lines = [
        "# Exhaustive Legal & Jurisprudence Dictionary for WM Keyboard (langId=en)",
        "# Comprehensive coverage of Latin maxims, statutory law, constitutional law, civil procedure, contracts, torts, corporate/IP law, criminal procedure, and courtroom terminology."
    ]
    for term, val in sorted_terms:
        lines.append(f"{term} {val}")
        
    os.makedirs(OUTPUT_FILE.parent, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
        
    print(f"Generated {OUTPUT_FILE} with {len(sorted_terms)} unique legal terms.")

if __name__ == "__main__":
    generate_dictionary()
