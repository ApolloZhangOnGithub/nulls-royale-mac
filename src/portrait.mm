#import <UIKit/UIKit.h>

// Keep the game's original controller and renderer. Only constrain its window.
static void configurePortrait(void) {
    for (UIScene *scene in UIApplication.sharedApplication.connectedScenes) {
        if (![scene isKindOfClass:UIWindowScene.class]) continue;
        UISceneSizeRestrictions *limits = ((UIWindowScene *)scene).sizeRestrictions;
        if (!limits) continue;
        limits.minimumSize = CGSizeMake(540, 960);
        limits.maximumSize = CGSizeMake(540, 960);
        limits.allowsFullScreen = NO;
    }
}

__attribute__((constructor)) static void installPortrait(void) {
    @autoreleasepool {
        [NSNotificationCenter.defaultCenter
            addObserverForName:UISceneDidActivateNotification
            object:nil queue:NSOperationQueue.mainQueue
            usingBlock:^(NSNotification *notification) { configurePortrait(); }];
    }
}
