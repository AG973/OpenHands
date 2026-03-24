"""Mobile App Building tool for the CodeAct Agent.

Provides the agent with capabilities to create, build, and deploy
mobile applications using React Native and Expo.
"""

from litellm import ChatCompletionToolParam, ChatCompletionToolParamFunctionChunk

_MOBILE_BUILD_DESCRIPTION = """Build, test, and deploy mobile applications for iOS and Android using React Native/Expo. Full pipeline from project creation to app store submission, with automated testing on both platforms.

### Available Operations:

**Project Setup:**
1. **create_project** - Create a new React Native/Expo project from a template.
2. **install_dependencies** - Install project dependencies (npm/yarn).
3. **add_package** - Add a package to the mobile project.
4. **setup_eas_config** - Generate eas.json and configure EAS Build (app name, bundle IDs).

**Development:**
5. **start_dev_server** - Start the Expo/React Native development server.
6. **generate_component** - Generate a new React Native component.
7. **generate_screen** - Generate a new screen/page.

**Building:**
8. **build_android** - Build Android APK/AAB (auto-selects local Gradle or EAS cloud).
9. **build_ios** - Build iOS app via EAS Build (cloud — no Mac required).
10. **build_web** - Build the web version of the app (Expo web).
11. **eas_build** - Trigger a cloud build using Expo Application Services (EAS).

**Testing — Maestro UI Automation (iOS + Android):**
12. **setup_maestro** - Install Maestro CLI for automated UI testing.
13. **create_maestro_flow** - Create a YAML test flow (e.g., login, signup, checkout).
14. **run_maestro_test** - Run Maestro UI tests on Android or iOS separately.
15. **run_maestro_studio** - Start Maestro Studio for visual interactive test building.

**Testing — Cloud Devices (Appetize.io):**
16. **upload_to_appetize** - Upload APK/IPA to test in browser (no emulator needed).
17. **get_appetize_embed_url** - Get embeddable URL for specific device/OS version.

**Testing — Local Emulator:**
18. **start_android_emulator** - Start an Android emulator (requires Android SDK).
19. **install_apk_on_device** - Install APK on connected device/emulator via ADB.

**Testing — Unit Tests:**
20. **run_tests** - Run the project's Jest unit test suite.

**Deployment:**
21. **eas_submit_android** - Submit to Google Play Store via EAS.
22. **eas_submit_ios** - Submit to Apple App Store via EAS.
23. **publish_update** - Publish an over-the-air update via EAS Update.
24. **preview_qr** - Generate QR code for Expo Go preview on real device.

### Testing Workflow:
1. Build: `build_android` (APK) or `build_ios` (IPA via EAS)
2. Test locally: `start_android_emulator` + `install_apk_on_device` + `run_maestro_test platform=android`
3. Test in cloud: `upload_to_appetize` + `get_appetize_embed_url` (works for both iOS and Android, no emulator needed)
4. Test iOS separately: `run_maestro_test platform=ios` (requires iOS simulator or Appetize)

### Environment Variables:
- EXPO_TOKEN — for EAS Build/Submit operations
- APPETIZE_API_TOKEN — for cloud device testing on Appetize.io
- ANDROID_HOME — for local Android builds and emulator
"""

MobileBuildTool = ChatCompletionToolParam(
    type='function',
    function=ChatCompletionToolParamFunctionChunk(
        name='mobile_build',
        description=_MOBILE_BUILD_DESCRIPTION,
        parameters={
            'type': 'object',
            'properties': {
                'operation': {
                    'type': 'string',
                    'description': 'The mobile build operation to perform.',
                    'enum': [
                        'create_project',
                        'install_dependencies',
                        'add_package',
                        'start_dev_server',
                        'setup_eas_config',
                        'generate_component',
                        'generate_screen',
                        'build_android',
                        'build_ios',
                        'build_web',
                        'eas_build',
                        'setup_maestro',
                        'create_maestro_flow',
                        'run_maestro_test',
                        'run_maestro_studio',
                        'upload_to_appetize',
                        'get_appetize_embed_url',
                        'start_android_emulator',
                        'install_apk_on_device',
                        'run_tests',
                        'preview_qr',
                        'eas_submit_android',
                        'eas_submit_ios',
                        'publish_update',
                    ],
                },
                'project_name': {
                    'type': 'string',
                    'description': 'Name of the mobile project to create.',
                },
                'project_path': {
                    'type': 'string',
                    'description': 'Path to the mobile project directory.',
                },
                'template': {
                    'type': 'string',
                    'description': 'Project template to use (blank, tabs, drawer, stack, ecommerce, social, chat).',
                    'enum': ['blank', 'tabs', 'drawer', 'stack', 'ecommerce', 'social', 'chat'],
                },
                'platform': {
                    'type': 'string',
                    'description': 'Target platform for build operations.',
                    'enum': ['android', 'ios', 'web', 'all'],
                },
                'component_name': {
                    'type': 'string',
                    'description': 'Name of the component or screen to generate.',
                },
                'component_description': {
                    'type': 'string',
                    'description': 'Description of the component or screen functionality for code generation.',
                },
                'package_name': {
                    'type': 'string',
                    'description': 'NPM package name to add (add_package operation).',
                },
                'navigation_type': {
                    'type': 'string',
                    'description': 'Type of navigation to set up.',
                    'enum': ['stack', 'tab', 'drawer', 'bottom-tab'],
                },
                'build_profile': {
                    'type': 'string',
                    'description': 'EAS build profile (development, preview, production).',
                    'enum': ['development', 'preview', 'production'],
                },
                'build_type': {
                    'type': 'string',
                    'description': 'Build output type for Android.',
                    'enum': ['apk', 'aab'],
                },
                'flow_name': {
                    'type': 'string',
                    'description': 'Name of the Maestro test flow (e.g., login, signup, checkout).',
                },
                'flow_steps': {
                    'type': 'array',
                    'description': 'List of Maestro flow steps as objects (e.g., [{"tapOn": "Login"}, {"assertVisible": "Welcome"}]).',
                    'items': {'type': 'object'},
                },
                'app_path': {
                    'type': 'string',
                    'description': 'Path to APK/IPA file (for upload_to_appetize, install_apk_on_device).',
                },
                'public_key': {
                    'type': 'string',
                    'description': 'Appetize.io public key (from upload_to_appetize result).',
                },
                'device': {
                    'type': 'string',
                    'description': 'Device model for Appetize.io (e.g., pixel7, iphone15pro).',
                },
                'os_version': {
                    'type': 'string',
                    'description': 'OS version for Appetize.io (e.g., 14.0, 17.0).',
                },
                'avd_name': {
                    'type': 'string',
                    'description': 'Android Virtual Device name for emulator.',
                },
                'app_name': {
                    'type': 'string',
                    'description': 'Application display name (for setup_eas_config).',
                },
                'android_package': {
                    'type': 'string',
                    'description': 'Android package name (e.g., com.myapp.example) for setup_eas_config.',
                },
                'ios_bundle': {
                    'type': 'string',
                    'description': 'iOS bundle identifier (e.g., com.myapp.example) for setup_eas_config.',
                },
            },
            'required': ['operation'],
        },
    ),
)
