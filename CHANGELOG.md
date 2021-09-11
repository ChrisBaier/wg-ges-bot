# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.1.0] - 2021-09-11
### Fixed
- Removed legacy handling of now  non-existent error case.
- Updated the class selector for ads.
- Changed wrong path in Dockerfile for build.
- Log to console instead of file for logging.
- Removed failing fake_useragent package.

### Changed
- Reduced initial delay to 5 seconds.
- Deleted unused torrc file.
- Removed unused imports and torrequest package.
- Added square meter unit to generated chat message.
- Updated all feature selectors to current page-structure.
- Added more verbose exception logging.
- Removed more tor-specific code.
- Replaced tor requests with normal ones.
- Added more verbose exception logging for logging.
- Fixed path to main executable script for dockerfile.
- Sorted files into src and res directories for fs.
- Added simple Docker configuration for tor.
- Added save_ids to make restarting more stable even with bugs.
- Deleted wrong requirement.
- Set to prod token.
- Added url to message and set it to not preview the page.
- Refactoring, less verbose texts, more safety when deleting filters.
- Fixed subscribe, unsubscribe bugs. subscribing multiple cities should work now.
- Added AvailableFrom and AvailableTo filters. made Ad.from_dict static, also some minor reformatting.
- Added explanations to params_template.
- Updated requirements.txt.
- Added installation instructions to readme.
- Fix scraping as they changed their site layout.
- Shorter readme.
- Merge pull request #4 from roschaefer/master.
- Merge branch 'master' into master.
- Refactor original script.
- Remove All_filters().
- Subscribe#subscribe adds City Filter.
- Implement Subscriber#already_had.
- Implement str method to see all filters of subscriber.
- Implement already_had behaviour in Subscriber.
- Move all classes in dedicated file.
- Test case for FilterCity.
- Implement already_had with sets.
- Implement FilterAvailability.
- Merge branch 'master' of https://github.com/Lauchturm/wg-ges-bot.
- Added error handler to dispatcher.
- Added cmd /current_count.
- Implement Ad.to_chat_message().
- Merge pull request #3 from roschaefer/refactoring.
- Amend.
- Rename offer to ad (proper translation).
- Implement + Test gender filter.
- Implement+Test delete_filter.
- Requirements for pytest.
- Start to write OOP.
- Remove unnecessary HTTP request header.
- Set up software tests with py.test.
- Cmd /current_offers returns offers of *all* cities.
- Refactor if-clauses with list comprehensions.
- Remove code duplication.
- Merge branch 'master' of https://github.com/Lauchturm/wg-ges-bot.
- Refactoring.
- Added global var 'active_subs' and changed some functions to using that.
- Refactored logging.
- Merge pull request #2 from roschaefer/add_requirements_and_default_params_template.
- Typo.
- Provide a params template.
- List dependencies in requirements.txt.
- Bughunt. parsemode markdown and using underscores with different meanings such as in /filter_rent failed (obviously).
- Added karlsruhe bot to readme.
- Catching unauthorized exceptions (when someone blocked the bot, but has running jobs).
- English readme, cleanup.
- First commit.
- Initial commit.

[Unreleased]: https://github.com/ChrisBaier/wg-ges-bot/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/ChrisBaier/wg-ges-bot/releases/tag/v1.1.0
