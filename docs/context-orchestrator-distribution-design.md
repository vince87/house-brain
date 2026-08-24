# Context Orchestrator and Home Assistant distribution

This document defines the architecture for the combined development block. It is
an implementation contract: security rules in this document are requirements,
not optional behaviour.

## Goals

The work has two connected parts:

1. reduce the Home Assistant context supplied to the model through configurable,
   deterministic logical views;
2. make the native Home Assistant integration installable and updatable through
   a documented distribution path while keeping the generic container supported.

The connection between the two parts is the Home Assistant administration
experience. An administrator can configure and preview context views from the
native panel, then use the same integration package across manual and HACS
installations.

## Non-goals

This work does not:

- publish a tag or release;
- grant access to entities not allowed by the global autonomy policy;
- infer permissions from areas, devices, domains, labels, names, or views;
- expose the Docker socket;
- silently migrate, overwrite, or delete persistent data;
- remove the standalone Docker Compose deployment;
- add action parsing based on natural-language keywords;
- add special cases for particular domains or devices.

## Security model

The autonomy policy remains the only authority for entity visibility and
control. A context view is a selection applied after that policy.

The effective entity set is:

    policy-visible entities INTERSECT selected view

A view can therefore narrow the set, but can never widen it. Controllability is
calculated independently by the existing policy and action engine. Selecting an
entity in a view does not make it controllable.

Home Assistant hidden entities remain inaccessible. Exclusions and other
existing global restrictions keep their current precedence.

Every request path that accepts a view identifier must resolve the view
server-side. Unknown, disabled, or ambiguous identifiers fail explicitly; the
server must not silently select a different view.

## Persistent configuration

Logical views use an optional dedicated file:

    /config/context-views.yaml

The file is inside the existing single persistent bind mount and is therefore
included in whole-config backups and restores. Its absence preserves current
behaviour.

The first schema version is intentionally small:

    version: 1
    default_view: null
    views:
      - id: example_ground_floor
        name: Example ground floor
        enabled: true
        areas:
          - example_ground_floor
        domains:
          - light
          - cover
        entities:
          - sensor.example_temperature
        max_entities: 40
        include_linked_memories: true

Rules:

- identifiers are stable, unique, and language-independent;
- names are presentation metadata and may be localized by the user;
- selectors are combined as a union, then intersected with the policy;
- an empty selector set matches no entities;
- max_entities has a bounded server-side range;
- duplicate and invalid selectors are rejected;
- real household entity names never appear in repository defaults or examples.

## Deterministic context selection

A caller may provide an explicit view_id. Explicit selection is authoritative
after validation.

For requests without an explicit view:

1. preserve explicit entity IDs already present in the structured request;
2. use a configured default view when one exists;
3. otherwise preserve the current policy-filtered context behaviour.

The server does not select views with language-specific regular expressions or
keyword lists. A model may request a view through a structured tool call, but
the server validates the identifier and all resulting entities.

Entity ordering is stable:

1. explicit structured entities;
2. entities linked to relevant verified memories;
3. remaining view entities in deterministic entity-ID order.

The configured maximum is applied only after required explicit entities have
been retained. Omitted counts are reported without leaking hidden entity IDs.

## Tools and trace

The planned structured interfaces are:

- list_context_views: list enabled views and selector summaries;
- preview_context_view: show the effective policy-safe selection;
- get_home_context(view_id=...): apply a selected view.

Tool trace records:

- selected view ID or the absence of a view;
- selection source (explicit, default, or none);
- selected, returned, and omitted counts;
- whether a limit was applied;
- counts of verified and unverified linked memories.

Trace data must not disclose API keys, authorization codes, hidden entities, or
memory query text.

## Administration API and UI

Administration endpoints provide validated read, preview, replace, and delete
operations. Writes use the same atomic replacement and recoverable backup
principles as the autonomy configurator.

The UI provides:

- a dedicated context page;
- view list, create, edit, disable, and delete flows;
- selectors for areas, domains, and policy-visible entities;
- a live preview with selected and omitted counts;
- a clear statement that views do not grant permissions;
- responsive layout consistent with the Home Assistant-style management UI.

The native Home Assistant panel exposes the same functions through authenticated
admin-only WebSocket commands. Direct House Brain access continues to require
the House Brain API key.

## HACS distribution

The custom integration remains under custom_components/house_brain. The HACS
path must include:

- valid hacs.json metadata;
- a versioned integration manifest;
- a release archive containing the expected integration directory;
- automated validation of archive layout and manifest/version consistency;
- documented custom-repository installation and upgrade;
- rollback instructions using the previous release archive.

A release workflow may prepare an artifact, but this PR does not create or
publish a tag without explicit approval.

## Home Assistant add-on evaluation

The add-on is developed as an isolated, opt-in distribution prototype. It must:

- keep the generic GHCR/container deployment available;
- use Home Assistant Supervisor APIs rather than a Docker socket;
- persist data in the add-on data directory;
- expose the web interface through ingress;
- support explicit import from a whole-config backup;
- validate a backup before import and retain a recoverable pre-import copy;
- never discover, stop, replace, or delete an existing standalone container.

The add-on prototype is not declared production-ready until it passes build
validation on supported architectures and a real Supervisor installation test.

## Compatibility and rollout

When context-views.yaml is absent, API, chat, events, MCP, Assist, and AI Task
retain their current behaviour. Existing autonomy and database files require no
migration.

Implementation is delivered in phases within one pull request:

1. schema, persistence, selection engine, and unit tests;
2. agent tools, trace, API, and large-registry regression tests;
3. direct UI and native Home Assistant panel;
4. HACS release artifact validation and documentation;
5. add-on prototype and migration runbook;
6. complete Python, Ruff, JavaScript, hassfest, archive, and multi-architecture
   validation;
7. real-server test checklist supplied to the user.

No merge, tag, release, or destructive migration is performed without explicit
approval.
