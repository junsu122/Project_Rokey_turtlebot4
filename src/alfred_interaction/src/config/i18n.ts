import { useLanguage, type AppStrings, type Language } from '@/core/i18n';

/**
 * Full UI translations (requirement ver02 §2.5.3 — ko/en/ja/zh).
 * Swap or extend a catalog to retune wording for a whole language at once.
 */
const ko: AppStrings = {
  app: { title: 'ALFRED 역사 안내 로봇' },
  lang: { label: '언어' },
  patrol: {
    hint: '사용하려면 화면을 터치하세요',
    wakeHint: '또는 "헬로 알프레드"라고 말해보세요 · 음성 안내',
    voicePrompt:
      '지하철 안내로봇 알프레드입니다. 음성 안내를 원하시면 헬로 알프레드라고 말해주세요.',
  },
  home: {
    greeting: (station) => `안녕하세요, ${station} 안내로봇 알프레드예요`,
    question: '무엇을 도와드릴까요?',
    buttonA: '시설 안내',
    buttonADesc: '지도에서 찾기',
    buttonB: '음성 안내',
    buttonBDesc: '말로 찾기',
    staffCall: '직원 호출',
  },
  map: {
    title: '어디로 안내해 드릴까요?',
    subtitle: '가고 싶은 시설을 눌러주세요',
    floorPickerLabel: '층 선택',
    here: '현위치',
    back: '뒤로',
    train: '열차',
  },
  voice: {
    title: '무엇이 궁금하세요?',
    idleHint: '아래 버튼을 누르고 말씀해 주세요',
    tapToSpeak: '눌러서 말하기',
    listening: '듣고 있어요…',
    stop: '말하기 끝',
    thinking: '생각하고 있어요…',
    youSaid: '이렇게 들었어요',
    answerLabel: '답변',
    notFound: '잘 못 들었어요. 다시 말씀해 주세요',
    error: '음성 인식에 문제가 생겼어요. 다시 시도해 주세요',
    confirmQuestion: (name) => `${name}(으)로 안내할까요?`,
    confirmYes: '네, 안내해주세요',
    confirmRetry: '다시 말하기',
    askAgain: '다시 묻기',
    back: '뒤로',
  },
  guiding: {
    caption: '시설 안내중',
    toDestination: (name) => `${name} (으)로 안내하고 있어요`,
    viaTransfer: (via, toFloor) =>
      `${via}(으)로 이동 후 ${toFloor}에서 이어서 안내해요`,
    handoff: (toFloor) => `${toFloor} 로봇이 이어서 안내해 드려요`,
    arrived: '도착했어요!',
    cancel: '안내 취소',
  },
  staff: {
    title: '직원이 오고 있습니다',
    description: '잠시만 기다려 주세요.',
    note: '※ 직원이 확인 후 닫기를 눌러주세요',
    close: '닫기',
  },
};

const en: AppStrings = {
  app: { title: 'ALFRED Station Guide Robot' },
  lang: { label: 'Language' },
  patrol: {
    hint: 'Touch the screen to start',
    wakeHint: 'Or say "Hello Alfred" · voice guidance',
    voicePrompt:
      'This is Alfred, the station guide robot. For voice guidance, say "Hello Alfred".',
  },
  home: {
    greeting: (station) => `Hi, I'm ALFRED, your guide at ${station}`,
    question: 'How can I help you?',
    buttonA: 'Find a place',
    buttonADesc: 'Pick on the map',
    buttonB: 'Ask by voice',
    buttonBDesc: 'Just say it',
    staffCall: 'Call staff',
  },
  map: {
    title: 'Where would you like to go?',
    subtitle: 'Tap the place you want',
    floorPickerLabel: 'Select floor',
    here: 'You are here',
    back: 'Back',
    train: 'Train',
  },
  voice: {
    title: 'What can I help with?',
    idleHint: 'Press the button below and speak',
    tapToSpeak: 'Tap to speak',
    listening: 'Listening…',
    stop: 'Done',
    thinking: 'Thinking…',
    youSaid: 'I heard',
    answerLabel: 'Answer',
    notFound: "Sorry, I didn't catch that. Please try again",
    error: 'Something went wrong with speech recognition. Please try again',
    confirmQuestion: (name) => `Shall I guide you to ${name}?`,
    confirmYes: 'Yes, please',
    confirmRetry: 'Speak again',
    askAgain: 'Ask again',
    back: 'Back',
  },
  guiding: {
    caption: 'Guiding you',
    toDestination: (name) => `Guiding you to ${name}`,
    viaTransfer: (via, toFloor) =>
      `Via the ${via}, then continuing on ${toFloor}`,
    handoff: (toFloor) => `The ${toFloor} robot will take over from here`,
    arrived: 'We have arrived!',
    cancel: 'Cancel',
  },
  staff: {
    title: 'A staff member is on the way',
    description: 'Please wait a moment.',
    note: '※ Staff will press Close after assisting',
    close: 'Close',
  },
};

const ja: AppStrings = {
  app: { title: 'ALFRED 駅案内ロボット' },
  lang: { label: '言語' },
  patrol: {
    hint: 'ご利用の際は画面にタッチしてください',
    wakeHint: 'または「ハロー アルフレッド」と話しかけてください · 音声案内',
    voicePrompt:
      '駅案内ロボット、アルフレッドです。音声案内をご希望の方は「ハロー アルフレッド」とお話しください。',
  },
  home: {
    greeting: (station) => `こんにちは、${station}のご案内ロボット、アルフレッドです`,
    question: 'ご用件をどうぞ',
    buttonA: '施設案内',
    buttonADesc: '地図から探す',
    buttonB: '音声案内',
    buttonBDesc: '話して探す',
    staffCall: '係員を呼ぶ',
  },
  map: {
    title: 'どちらへご案内しましょうか？',
    subtitle: '行きたい施設を押してください',
    floorPickerLabel: 'フロア選択',
    here: '現在地',
    back: '戻る',
    train: '列車',
  },
  voice: {
    title: 'ご質問をどうぞ',
    idleHint: '下のボタンを押して話してください',
    tapToSpeak: '押して話す',
    listening: '聞いています…',
    stop: '話し終わり',
    thinking: '考えています…',
    youSaid: 'このように聞こえました',
    answerLabel: '回答',
    notFound: 'うまく聞き取れませんでした。もう一度お願いします',
    error: '音声認識に問題が発生しました。もう一度お試しください',
    confirmQuestion: (name) => `${name}へご案内しますか？`,
    confirmYes: 'はい、お願いします',
    confirmRetry: 'もう一度話す',
    askAgain: 'もう一度きく',
    back: '戻る',
  },
  guiding: {
    caption: 'ご案内中',
    toDestination: (name) => `${name}へご案内しています`,
    viaTransfer: (via, toFloor) =>
      `${via}へ移動後、${toFloor}で続けてご案内します`,
    handoff: (toFloor) => `${toFloor}のロボットが続けてご案内します`,
    arrived: '到着しました！',
    cancel: '案内を中止',
  },
  staff: {
    title: '係員が向かっています',
    description: '少々お待ちください。',
    note: '※ 係員が確認後に「閉じる」を押します',
    close: '閉じる',
  },
};

const zh: AppStrings = {
  app: { title: 'ALFRED 车站向导机器人' },
  lang: { label: '语言' },
  patrol: {
    hint: '使用请触摸屏幕',
    wakeHint: '或说 "Hello Alfred" · 语音向导',
    voicePrompt: '我是车站向导机器人 Alfred。需要语音向导请说 "Hello Alfred"。',
  },
  home: {
    greeting: (station) => `您好，我是${station}的向导机器人 ALFRED`,
    question: '需要什么帮助？',
    buttonA: '设施向导',
    buttonADesc: '在地图上查找',
    buttonB: '语音向导',
    buttonBDesc: '说出来查找',
    staffCall: '呼叫工作人员',
  },
  map: {
    title: '想去哪里？',
    subtitle: '请点击您想去的设施',
    floorPickerLabel: '选择楼层',
    here: '当前位置',
    back: '返回',
    train: '列车',
  },
  voice: {
    title: '有什么可以帮您？',
    idleHint: '请按下方按钮后说话',
    tapToSpeak: '点击说话',
    listening: '正在聆听…',
    stop: '说完了',
    thinking: '正在思考…',
    youSaid: '我听到的是',
    answerLabel: '回答',
    notFound: '没有听清，请再说一次',
    error: '语音识别出现问题，请重试',
    confirmQuestion: (name) => `要为您带路到${name}吗？`,
    confirmYes: '好的，请带路',
    confirmRetry: '再说一次',
    askAgain: '再问一次',
    back: '返回',
  },
  guiding: {
    caption: '正在带路',
    toDestination: (name) => `正在带您前往${name}`,
    viaTransfer: (via, toFloor) => `先前往${via}，再在${toFloor}继续带路`,
    handoff: (toFloor) => `${toFloor}的机器人将继续为您带路`,
    arrived: '已到达！',
    cancel: '取消向导',
  },
  staff: {
    title: '工作人员正在赶来',
    description: '请稍候。',
    note: '※ 工作人员确认后会点击关闭',
    close: '关闭',
  },
};

export const messages: Record<Language, AppStrings> = { ko, en, ja, zh };

/** The active language's strings. Use inside components. */
export function useStrings(): AppStrings {
  return messages[useLanguage().language];
}
