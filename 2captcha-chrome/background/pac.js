var bypassList = [];

var proxyHost = null;

browser.runtime.onMessage.addListener((message) => {
    proxyHost = message.host;
    bypassList = message.bypassList;
});

function FindProxyForURL(url, host) {
    if (bypassList.includes(host)) return 'DIRECT';
    if (host == proxyHost) return 'PROXY 138.201.91.1:3128';
    return 'DIRECT';
}