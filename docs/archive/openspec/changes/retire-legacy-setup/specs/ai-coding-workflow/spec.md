# ai-coding-workflow Delta Specification

## ADDED Requirements

### Requirement: Legacy setup guidance does not override task authorization

Setup documentation SHALL describe explicit adoption scope and SHALL NOT treat reading a document as permission to change global settings, enable permission bypass, or install unrelated packages. Optional skills SHALL NOT be reported as required dependencies solely because they appear in a static catalog.

#### Scenario: User reads setup documentation

- GIVEN a user or agent reads a setup guide
- WHEN no installation or global configuration change has been requested
- THEN the guide SHALL NOT instruct the agent to execute global writes automatically

#### Scenario: Existing installer hook remains configured

- GIVEN a user settings file still references `skills/install-skills/check-skills.sh`
- WHEN the hook runs after catalog retirement
- THEN it SHALL exit successfully without output, installation, or configuration mutation

#### Scenario: User requests a specific skill

- GIVEN the user explicitly requests a skill installation
- WHEN the installer prepares it
- THEN it SHALL verify the requested source and destination and limit changes to the authorized scope
- AND it SHALL NOT install all previously cataloged packages or infer approval to overwrite existing files
