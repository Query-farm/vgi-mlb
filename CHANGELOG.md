# Changelog

All notable changes to this project are documented here.

## [Unreleased]

- Preserve earlier player-stat pages when MLB returns an empty terminal page.
- Reuse HTTP connections, bound concurrent upstream requests, honor
  `Retry-After`, and enforce a total query deadline.
- Require explicit signing and authentication policy for HTTP deployments.
- Add portable installation, container, CI, and trusted-publishing support.
- Add dependency compatibility bounds and production regression tests.

## [0.2.0]

- Add batting, pitching, fielding, advanced statistics, career totals, team
  splits, and game logs.
- Add typed Arrow schemas, cache-policy forwarding, agent metadata, and Haybarn
  end-to-end coverage.
