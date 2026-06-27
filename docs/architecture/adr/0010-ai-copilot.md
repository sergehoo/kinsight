# ADR-0010 — K-Insight AI Copilot (assistant gouverné, multi-provider, actionnable)

Statut : accepté (Phase 1 livrée) · Date : 2026-06-27

## Contexte
Transformer l'IA de K-Insight en assistant virtuel : analyser, expliquer, guider, générer
des rapports, configurer des intégrations et exécuter des actions métier — **sous contrôle
des permissions et de la validation utilisateur**. Contraintes fondatrices du projet :
l'IA ne doit **jamais inventer** de donnée (ADR-0007) et le périmètre RBAC (ADR-0005) +
l'audit s'appliquent partout.

## Décision

### 1. Ancrage avant génération (jamais d'invention)
Les **faits** (métrique du catalogue, valeur du mart ou N/D, source) sont calculés en amont
par `semantic.grounding` (déterministe, testé). Un LLM ne fait que **reformuler** autour de
ces faits ; il reçoit les faits + le contexte + la règle « ne jamais inventer ». Hors-ligne
ou si tous les LLM échouent, on renvoie la phrase ancrée déterministe. Une métrique hors
catalogue est **refusée** ; une valeur non branchée reste **N/D** avec proposition de
configurer la source.

### 2. Architecture multi-provider extensible avec fallback
`AIProviderRouter` essaie les providers par priorité : **DeepSeek (principal) → Claude
(fallback) → repli déterministe ancré** (toujours disponible, sans clé). Extensible (OpenAI,
Mistral). Chaque tentative trace provider / latence / erreur (`AIAuditLog`, champ `attempts`).
Clés via env : `DEEPSEEK_API_KEY`, `ANTHROPIC_API_KEY`.

### 3. Actions sous contrôle (lecture seule par défaut)
`ToolRegistry` déclare des outils {mode read|write, sensible, rôles requis}. Un outil de
**lecture** s'exécute immédiatement si l'utilisateur a les droits. Un outil d'**écriture /
sensible** n'est **jamais exécuté directement** : `PermissionAwareToolExecutor` crée une
`AIActionRequest` (statut `pending`) ; `ActionApprovalService.approve/reject` vérifie de
nouveau les droits puis exécute (ou rejette). RBAC contrôlé à la demande ET à l'approbation.
Suppression / email / notifications : **non activés** en Phase 1 (double validation prévue).

### 4. Contexte dynamique
`ContextBuilder` transmet à chaque message : utilisateur, rôle, périmètre, module/page,
filtres, période, filiale et **actions autorisées** (l'IA ne voit jamais un outil hors droits).

### 5. Modèles & API (Phase 1)
Modèles : `AIProvider, AIConversation, AIMessage, AITool, AIToolExecution, AIActionRequest,
AIActionApproval, AIAuditLog`. Endpoints sous `/api/v1/ai/` : `chat/`, `conversations/`,
`conversations/<id>/`, `tools/`, `tools/execute/`, `actions/`, `actions/<id>/approve|reject/`.

## Conséquences
- Le Copilot **fonctionne dès aujourd'hui** sans clé LLM (repli ancré), et monte en puissance
  dès que DeepSeek/Claude sont branchés — sans changer le contrat de gouvernance.
- Le tool-calling natif du LLM (boucle d'appels d'outils pilotée par le modèle), l'éditeur
  riche frontend, la génération/automatisation de rapports et les actions destructrices sont
  des **phases ultérieures** (différées : `AIKnowledgeContext, AIReport, AIAutomation`).
- Pour servir de **vraies valeurs** (au-delà de N/D), il faut les **bindings métrique→mart**
  par domaine (dépend des sources réelles, cf. backlog §0).

## Différé (phases suivantes)
2. Panel frontend premium (chat plein écran/sidebar, éditeur riche TipTap/Lexical, blocs
   KPI/alerte/rapport, sélecteur de contexte) · 3. Tool-calling LLM + génération de rapports
   (PDF/Excel/email) · 4. Actions destructrices sous double validation · 5. Automatisations
   planifiées (Celery Beat).
