#!/usr/bin/env python3
"""
Objections GENERALES - MiniBotPanel v3

Objections et FAQ communes a TOUTES les thematiques.
Ces objections peuvent etre utilisees seules ou combinees avec une thematique specifique.

Structure:
- Objections TEMPS (pas le temps, rappeler plus tard, etc.)
- Objections INTERET (pas interesse, aucun interet, etc.)
- Objections PRIX/BUDGET (trop cher, pas le budget, etc.)
- Objections HESITATION / INCERTITUDE (peut-etre, je sais pas, etc.)
- Objections REFLEXION (besoin de reflechir, parler au conjoint, etc.)
- Objections CONCURRENCE (deja un fournisseur, deja equipe, etc.)
- FAQ GENERALES (qui etes-vous, Bloctel, tarif, documentation, etc.)

Audio:
- Fichiers dans: audio/{voice}/objections/
- Noms: general_*.wav
"""

from typing import List
from system.objections_db import ObjectionEntry


# ═══════════════════════════════════════════════════════════════════════════
# OBJECTIONS GENERALES
# ═══════════════════════════════════════════════════════════════════════════

OBJECTIONS_DATABASE: List[ObjectionEntry] = [
    # ─────────────────────────────────────────────────────────────────────
    # TEMPS
    # ─────────────────────────────────────────────────────────────────────
    ObjectionEntry(
        keywords=[
            "pas le temps", "pas de temps", "pas le temps là",
            "occupé", "débordé", "surchargé", "submergé",
            "pas maintenant", "moment pas bon", "pas disponible",
            "j'ai pas le temps", "vraiment pas le temps",
            "là j'peux pas", "je suis pressé", "pressé",
            "j'ai autre chose", "autre chose à faire"
        ],
        response="Je comprends, votre temps est précieux. Je vous prends deux minutes chrono, je vérifie votre éligibilité, si c'est ok on fixe un rendez-vous avec notre expert à votre convenance selon vos disponibilités. On fait comme ça ?",
        audio_path="general_pas_temps.wav",
        entry_type="objection"
    ),

    ObjectionEntry(
        keywords=[
            "rappelez", "rappeler plus tard", "rappeler", "plus tard",
            "pas maintenant", "autre moment", "rappeler demain",
            "rappelez-moi", "rappelle plus tard", "recontacter",
            "un autre jour", "une autre fois", "la semaine prochaine"
        ],
        response="Justement, je vous prends deux minutes montre en main, on vérifie si vous rentrez dans les critères et on fixe un rendez-vous avec notre expert quand vous serez disponible. Ça marche ?",
        audio_path="general_rappeler.wav",
        entry_type="objection"
    ),

    ObjectionEntry(
        keywords=[
            "réunion", "en cours", "là je peux pas",
            "en rendez-vous", "en meeting", "occupé là",
            "je suis en voiture", "je conduis", "au volant",
            "je suis au travail", "au boulot", "en déplacement"
        ],
        response="Je comprends, vous n'êtes pas disponible. Alors venez, on prend deux minutes pour voir si vous rentrez dans les critères, et je vous fixe un rendez-vous à votre convenance, selon votre disponibilité, avec notre expert. Ça vous convient ?",
        audio_path="general_reunion.wav",
        entry_type="objection"
    ),

    ObjectionEntry(
        keywords=[
            "c'est trop long", "trop long", "ça prend trop de temps",
            "combien de temps", "dure combien", "je vais pas rester",
            "abrégez", "faites court"
        ],
        response="Deux minutes maximum, promis. Si après ça c'est pas pour vous, on se dit au revoir. On part là-dessus ?",
        audio_path="general_trop_long.wav",
        entry_type="objection"
    ),

    ObjectionEntry(
        keywords=[
            "mauvais numéro", "c'est pas le bon numéro", "vous vous êtes trompé",
            "trompé de numéro", "c'est pas moi", "erreur de numéro",
            "je suis pas la bonne personne"
        ],
        response="Soit c'est un mauvais numéro, soit c'est le destin. Ça prend deux petites minutes et ça peut peut-être vous intéresser. On y va ?",
        audio_path="general_mauvais_numero.wav",
        entry_type="faq"
    ),

    # ─────────────────────────────────────────────────────────────────────
    # INTERET
    # ─────────────────────────────────────────────────────────────────────
    ObjectionEntry(
        keywords=[
            "pas intéressé", "intéressé pas", "m'intéresse pas",
            "ça m'intéresse pas", "non merci", "merci non",
            "pas pour moi", "ça me dit rien", "pas convaincu",
            "aucun intérêt", "je suis pas intéressé", "pas vraiment",
            "non c'est bon", "c'est bon merci", "ça ira",
            "je veux pas",
            "ça m'intéresse vraiment pas", "aucun intérêt du tout",
            "pas du tout intéressé", "vraiment pas", "absolument pas",
            "jamais", "jamais de la vie", "certainement pas",
            "hors de question", "même pas en rêve"
        ],
        response="Je comprends que vous devez être sollicité souvent. Laissez-moi tenter ma chance en moins de trente secondes pour vous expliquer de quoi il en retourne. Si vous êtes intéressé, on continue. Et sinon, on aura eu juste le plaisir de faire connaissance. On fait comme ça ?",
        audio_path="general_pas_interesse.wav",
        entry_type="objection"
    ),

    # ─────────────────────────────────────────────────────────────────────
    # BUDGET / SITUATION
    # ─────────────────────────────────────────────────────────────────────
    ObjectionEntry(
        keywords=[
            "je suis retraité", "retraité", "à la retraite",
            "je suis au chômage", "chômage", "sans emploi",
            "étudiant", "je suis étudiant", "jeune"
        ],
        response="Pas de souci, ça n'empêche rien. On regarde ensemble si vous êtes éligible, c'est gratuit. On y va ?",
        audio_path="general_situation_vie.wav",
        entry_type="objection"
    ),

    ObjectionEntry(
        keywords=[
            "je suis pas concerné", "pas concerné", "ça me concerne pas",
            "j'ai pas de", "j'en ai pas", "je n'ai pas",
            "ça ne me concerne pas", "pas pour moi ça"
        ],
        response="C'est ce que beaucoup de nos clients disaient au début. Parfois on est concerné sans le savoir. On vérifie ensemble ? Ça prend deux minutes.",
        audio_path="general_pas_concerne.wav",
        entry_type="objection"
    ),

    # ─────────────────────────────────────────────────────────────────────
    # HESITATION / INCERTITUDE
    # ─────────────────────────────────────────────────────────────────────
    ObjectionEntry(
        keywords=[
            "peut-être", "peut être", "ptêtre", "p't'être",
            "on verra", "je vais voir", "je verrai", "faut voir",
            "bof",  # REMOVED: "mouais", "ouais" (trop ambigus - gardés uniquement dans affirm)
            "pourquoi pas", "à voir", "on va voir",
            "réfléchir", "besoin de temps", "hésiter", "hésitation",
            "dois réfléchir", "je vais réfléchir", "laisser réfléchir",
            "temps de réflexion", "besoin réfléchir",
            "faut que j'y pense", "laisser le temps", "prendre le temps"
        ],
        response="Je comprends l'hésitation. Les gens brillants décident sur des faits, pas sur des impressions. L'idéal ce serait quand même de vous entretenir avec notre expert pour qu'il vous explique tout. Ça vous convient ?",
        audio_path="general_hesitation.wav",
        entry_type="objection"
    ),

    ObjectionEntry(
        keywords=[
            "parler conjoint", "parler femme", "parler mari",
            "en parler", "parler ma femme", "parler mon mari",
            "décision à deux", "consulter conjoint",
            "demander à ma femme", "demander à mon mari",
            "voir avec mon épouse", "voir avec mon époux",
            "en discuter", "consulter ma moitié"
        ],
        response="C'est sage de décider à deux. Laissez-moi finir de vous poser les questions, comme ça vous aurez tous les éléments pour en parler ensemble. On continue ?",
        audio_path="general_parler_conjoint.wav",
        entry_type="objection"
    ),

    # ─────────────────────────────────────────────────────────────────────
    # CONCURRENCE
    # ─────────────────────────────────────────────────────────────────────
    ObjectionEntry(
        keywords=[
            "déjà un fournisseur", "déjà équipé", "déjà chez",
            "j'ai déjà", "déjà souscrit", "déjà un contrat",
            "déjà engagé", "déjà pris", "déjà quelqu'un",
            "j'ai ce qu'il faut", "c'est bon j'ai déjà",
            "je travaille déjà avec", "autre société", "autres courtiers",
            "autre courtier", "autre prestataire", "autres prestataires",
            "j'ai mon courtier", "j'ai mon prestataire", "j'ai ma société",
            "déjà un courtier", "déjà un prestataire",
            "je suis satisfait", "satisfait de mon", "content de mon",
            "j'ai pas besoin de changer", "rien à changer",
            "pas envie de changer", "je reste avec mon", "je garde mon"
        ],
        response="Vous avez raison de rester fidèle. Mais on ne met jamais ses œufs dans le même panier. Deux minutes pour voir si on fait mieux. On y va ?",
        audio_path="general_deja_fournisseur.wav",
        entry_type="objection"
    ),

    # ─────────────────────────────────────────────────────────────────────
    # FAQ GENERALES
    # ─────────────────────────────────────────────────────────────────────
    # NOTE: "c'est quoi" déplacé vers fichiers thématiques car réponse dépend du secteur

    ObjectionEntry(
        keywords=[
            "vous appelez d'où", "appelez d'où", "vous êtes où",
            "d'où vous appelez", "localisation", "vous êtes basé où",
            "vous êtes situé où", "votre adresse",
            "où sont vos bureaux", "où sont vos locaux", "adresse agence",
            "je peux venir", "passer vous voir"
        ],
        response="On est basé en France. Mais l'important c'est ce qu'on peut faire pour vous. Deux minutes pour vérifier votre éligibilité. Ça marche ?",
        audio_path="general_localisation.wav",
        entry_type="faq"
    ),

    # NOTE: "pourquoi m'appeler" et "comment ça marche" déplacés vers fichiers thématiques

    # NOTE: "je comprends pas" / "répéter" déplacé vers fichiers thématiques

    # NOTE: "qui êtes-vous" et "quelle société" déplacés vers fichiers thématiques
    # (objections_finance.py, objections_energie.py, etc.) pour réponses personnalisées

    ObjectionEntry(
        keywords=[
            "comment vous avez mon numéro", "d'où numéro",
            "qui vous a donné", "comment vous m'avez eu",
            "où vous avez trouvé", "mon numéro d'où",
            "comment vous avez eu mes coordonnées", "mes infos d'où"
        ],
        response="Vous avez, à un moment donné, manifesté un intérêt pour nos services. C'est la raison pour laquelle je vous rappelle pour voir où vous en êtes par rapport à votre projet. Deux minutes pour faire le point. On part là-dessus ?",
        audio_path="general_comment_numero.wav",
        entry_type="faq"
    ),

    ObjectionEntry(
        keywords=[
            "robot", "c'est un robot", "automatique", "enregistrement",
            "message automatique", "c'est une machine", "pas un humain",
            "ia", "intelligence artificielle", "chatbot", "bot",
            "voix synthétique", "voix artificielle", "généré par ordinateur",
            "vous êtes un robot", "parle à un robot",
            "vous êtes un humain", "vraie personne", "parle à quelqu'un",
            "c'est réel", "parle à un vrai"
        ],
        response="C'est étonnant que vous me disiez ça, vous n'êtes pas la première personne à me le dire. Mais non, je vous rassure, vous parlez bien avec une vraie personne. On continue ?",
        audio_path="general_robot.wav",
        entry_type="faq"
    ),

    ObjectionEntry(
        keywords=[
            "c'est gratuit", "ça coûte quoi", "tarif", "combien",
            "quel prix", "coût"
        ],
        response="Dans un premier temps, c'est gratuit et sans engagement. L'idée c'est de répondre à quelques questions pour voir si vous êtes éligible, et notre expert vous rappelle pour tout vous expliquer. On y va ?",
        audio_path="general_tarif.wav",
        entry_type="faq"
    ),

    ObjectionEntry(
        keywords=[
            "envoyez documentation", "envoyez email", "envoyez brochure",
            "envoyez doc", "envoyer documentation", "envoyer brochure",
            "envoyer mail", "par écrit", "envoyez informations", "recevoir par mail",
            "envoyez par courrier", "par la poste", "courrier postal",
            "papier", "lettre", "envoyez moi une lettre"
        ],
        response="Bien sûr, avec plaisir. Mais pour vous envoyer de la documentation pertinente, j'ai besoin de quelques infos pour vérifier votre éligibilité. Ensuite je vous envoie tout ça et notre expert vous rappelle, gratuitement et sans engagement. Ça vous convient ?",
        audio_path="general_documentation.wav",
        entry_type="faq"
    ),

    ObjectionEntry(
        keywords=[
            "c'est sérieux", "arnaque", "fiable", "confiance",
            "vous êtes sérieux", "c'est une arnaque", "escroquerie",
            "escroc", "voleur", "piège", "attrape-nigaud", "faux",
            "fraude", "suspect", "louche", "bizarre", "pas confiance",
            "je fais pas confiance", "méfiant"
        ],
        response="Vous avez raison de vous méfier. Aujourd'hui on trouve à boire et à manger sur internet. Ce que nous vous proposons avant toute chose, c'est un entretien gratuit et sans engagement avec un expert qui vous donnera tous les détails. Ça vous convient ?",
        audio_path="general_serieux.wav",
        entry_type="faq"
    ),

    ObjectionEntry(
        keywords=[
            "engagement", "durée", "contrat", "résiliation",
            "durée engagement", "sans engagement"
        ],
        response="Justement, c'est gratuit et sans engagement. L'idée c'est de voir si vous rentrez dans les critères pour bénéficier d'un entretien avec un conseiller spécialisé. On fait comme ça ?",
        audio_path="general_engagement.wav",
        entry_type="faq"
    ),

    ObjectionEntry(
        keywords=[
            "j'ai pas demandé", "rien demandé", "pas sollicité",
            "j'ai jamais demandé", "pas demandé à être appelé"
        ],
        response="Je comprends. Vous avez dû manifester un intérêt à un moment donné, c'est pourquoi on vous rappelle. Mais les meilleures opportunités viennent sans qu'on les cherche. Deux minutes pour vérifier. On part là-dessus ?",
        audio_path="general_pas_demande.wav",
        entry_type="faq"
    ),

    ObjectionEntry(
        keywords=[
            "déjà appelé", "on m'a déjà appelé", "vous m'avez déjà appelé",
            "rappelé plusieurs fois", "arrêtez appeler"
        ],
        response="Je comprends, c'est un marché en plein essor donc d'autres ont pu vous contacter. Ça veut dire que ça marche bien. Donnez-moi ma chance trente secondes, je vous pose quelques questions et si vous êtes éligible notre spécialiste vous rappelle. Ça vous convient ?",
        audio_path="general_deja_appele.wav",
        entry_type="faq"
    ),

    ObjectionEntry(
        keywords=[
            "site internet", "votre site", "adresse web",
            "regarder en ligne", "voir sur internet"
        ],
        response="Bien sûr. Mais pour vous envoyer des informations pertinentes, j'ai besoin qu'on vérifie ensemble votre éligibilité. Ensuite notre expert vous rappelle avec tout ce qu'il vous faut. Ça marche ?",
        audio_path="general_site.wav",
        entry_type="faq"
    ),


    ObjectionEntry(
        keywords=[
            "on m'a dit que", "j'ai entendu dire", "il paraît que",
            "apparemment", "j'ai lu que", "on dit que"
        ],
        response="C'est un domaine en plein essor, donc il y a beaucoup de fausses informations qui circulent. L'idéal serait de prendre deux minutes pour les questions et convenir d'un rendez-vous avec notre expert qui vous donnera les vraies réponses. On y va ?",
        audio_path="general_rumeurs.wav",
        entry_type="faq"
    ),

    # NOTE: "prefere_deplacer" déplacé vers objections_finance.py (réponse spécifique par thématique)

    # Note: RATTRAPAGE ABANDON (retry_global) deplace vers le scenario principal
    # pour une meilleure gestion du flow (voir create_scenario.py)

    # ─────────────────────────────────────────────────────────────────────
    # INTENTS DE BASE (pour navigation, pas de réponse audio)
    # ─────────────────────────────────────────────────────────────────────
    ObjectionEntry(
        keywords=[
            # Oui variations (clairs et directs)
            "oui", "oui oui", "ouais", "mouais",
            # D'accord variations
            "d'accord", "dac", "daccord", "ok", "okay", "oki",
            # Absolument / Exactement
            "absolument", "exactement", "tout à fait", "bien sûr", "évidemment",
            "carrément", "clairement", "sans problème", "avec plaisir",
            # Affirmations directes
            "je suis intéressé", "ça m'intéresse", "je veux bien",
            "volontiers", "je suis d'accord", "allons-y", "parfait",
            "ça peut se passer", "ça peut se faire", "ça peut le faire",
            # Validation
            "c'est bon", "c'est parfait", "ça marche", "ça me va", "entendu",
            "compris", "validé", "je valide", "go", "banco"
        ],
        response="",  # Pas d'audio pour les intents de navigation
        audio_path="",
        entry_type="affirm"
    ),

    ObjectionEntry(
        keywords=[
            # Moments de la journée
            "matin", "le matin", "ce matin", "demain matin",
            "après-midi", "l'après-midi", "cet après-midi",
            "soir", "ce soir", "demain soir", "en soirée",
            # Jours de la semaine
            "lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche",
            # Périodes
            "semaine prochaine", "la semaine prochaine", "cette semaine",
            "demain", "après-demain"
        ],
        response="",  # Pas d'audio pour les intents de navigation
        audio_path="",
        entry_type="time"
    ),

    ObjectionEntry(
        keywords=[
            # Incertitude directe
            "je sais pas", "sais pas", "je ne sais pas", "j'en sais rien",
            "je suis pas sûr", "pas sûr", "pas certain", "incertain",
            "je suis pas sur", "pas sur",  # sans accent
            # Hésitation vocale (mots-tampons)
            "euh", "hum", "hmm", "ben", "bah",
            # Expressions d'incertitude
            "aucune idée", "chais pas", "jsp"
        ],
        response="",  # Pas d'audio pour les intents de navigation
        audio_path="",
        entry_type="unsure"
    ),

    ObjectionEntry(
        keywords=[
            # Non variations (simples, sans contexte)
            "non", "nan", "non non", "non non non", "nan nan", "nope", "négatif",
            # Refus poli (courts)
            "ça va", "c'est gentil mais non",
            "je passe", "je décline",
            # Refus direct
            "arrêtez", "stop", "laissez tomber", "laisser tomber",
            "j'arrête", "on arrête", "terminé", "fini"
        ],
        response="",  # Pas d'audio pour les intents de navigation
        audio_path="",
        entry_type="deny"
    ),

    ObjectionEntry(
        keywords=[
            # Insultes
            "con", "connard", "merde", "putain", "enculé", "va te faire",
            "va niquer", "ferme ta gueule", "casse-toi", "dégage",
            "abruti", "débile", "crétin", "imbécile", "connasse",
            "salaud", "salope", "ta gueule", "fous le camp",
            "fils de pute", "nique ta mère", "ntm", "fdp", "pute",
            "batard", "bâtard", "pd", "pédé", "enc", "tg",
            # Demande de retrait agressive
            "dérangez", "embêtez", "vous me dérangez", "arrêtez de m'appeler",
            "vous m'embêtez", "lâchez-moi", "fichez-moi la paix",
            "foutez-moi la paix", "laissez-moi tranquille",
            "rappeler jamais", "ne rappeler plus", "plus jamais",
            "retirez moi", "supprimez mon numéro",
            "effacez mon numéro", "m'appelez plus", "ne m'appelez plus",
            "plus d'appels", "stop aux appels", "je veux plus être appelé"
        ],
        response="",  # Pas d'audio pour les intents de navigation
        audio_path="",
        entry_type="insult"
    ),
]
