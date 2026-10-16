import { File } from 'expo-file-system';

// Expo SDK 57 makes the WinterCG-compliant `expo/fetch` the global fetch
// (see docs.expo.dev/versions/v57.0.0/sdk/expo — "On native platforms... the
// expo/fetch implementation becomes the global fetch by default"). Its
// FormData is spec-compliant and only knows how to send actual Blob/File
// parts — the classic React Native trick of appending a plain
// { uri, name, type } object (which only the old bridge's Networking module
// understood) is silently rejected, so the request never leaves the device.
// expo-file-system's File class implements Blob and works with it directly.
//
// Shared by every screen that uploads a document picked via
// expo-document-picker (registration, license reupload, shop creation).
export function toUploadFile(pickedDocument) {
  return new File(pickedDocument.uri);
}
